# Agenda Única P1020 — P10: origem do alias e desligamento da P anterior

Data: 22/11/2026.

## Sintomas

Após H10→P10:

1. o operador observou P9 ainda rodando por algum tempo após P10 já estar ativa;
2. o login em `agendaunica.cloudiff.duckdns.org` retornava `Origem não permitida`, embora a URL versionada funcionasse.

## Estado comprovado

No momento da auditoria:

- P10 estava `published/is_active=1`;
- P9 estava `published/is_active=0`;
- deployment P9 `dep_6c524d61f1a4dbe384f47364` estava `inactive` e seus containers `Exited`;
- deployment P10 `dep_00b101221eb813f671146b98` estava `production/running`;
- portanto P9 não consumia memória no estado final, mas o fluxo não esperava uma prova explícita de `inactive` antes de concluir.

## Correção do cutover

O Portal agora chama `_wait_deployment_inactive()` imediatamente após desativar a Produção anterior. O job só avança quando o Executor confirma `inactive` ou `removed`; se isso não ocorrer no prazo, o cutover falha em vez de declarar sucesso prematuro.

A mesma regra foi aplicada ao rollback: a Produção substituída deve confirmar Offline antes da finalização do estado no Portal.

## Causa da origem não permitida

O alias do Publisher era renderizado assim:

- navegador: `Origin: https://agendaunica.cloudiff.duckdns.org`;
- NPM alias: `Host` era forçado para `1020.cloudiff.duckdns.org`;
- aplicação Agenda compara `Origin` com `Host` como proteção CSRF;
- resultado: 403 `Origem não permitida`.

O renderer do Publisher foi corrigido para aliases preservarem `Host $host`, mantendo também `X-Forwarded-Host $host`. O upstream continua sendo o endereço estável numérico; somente a identidade HTTP pública deixa de ser sobrescrita.

## P10 — configuração explícita de Produção

A Produção P10 também carregava valores públicos herdados inadequados:

- `ALLOWED_ORIGINS` continha apenas o Portal CloudIFF;
- `APP_BASE_URL` ainda apontava para W3.

Foi feita edição humana normal no ambiente Produção, sem approval MCP separado:

- `ALLOWED_ORIGINS` passou a incluir Portal, P10 versionada, `1020` estável e `agendaunica`;
- `APP_BASE_URL` passou a usar o alias principal;
- revisão 87→88;
- apenas serviço `api` foi reconfigurado;
- deployment/volumes/snapshot foram preservados;
- secrets não foram expostos.

Essa edição é uma alteração explícita da Produção, compatível com o contrato que permite ajuste de variáveis depois da promoção. Ela não é uma transformação automática W→H→P.

## Provas

Após a correção, requests de login com Origin em:

- `https://1020-p10-publication.cloudiff.duckdns.org`;
- `https://1020.cloudiff.duckdns.org`;
- `https://agendaunica.cloudiff.duckdns.org`;

não retornam mais 403; com credencial deliberadamente inválida retornam 401, provando que a checagem de origem passou e a requisição chegou à autenticação.

Os três healthchecks seguem HTTP 200 na revisão `18416127cdf9`.
