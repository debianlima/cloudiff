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

O Publisher mantém `Host` numérico para o gateway localizar o backend e envia o host público em `X-Forwarded-Host`. O publication-gateway agora roteia pelo Host numérico, mas restaura um `X-Forwarded-Host` válido `*.cloudiff.duckdns.org` como `Host` ao encaminhar para a bridge. Assim a aplicação recebe a identidade pública correta sem quebrar o roteamento interno.

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

## Correção final da cadeia de proxy

Uma primeira hipótese de correção colocava `Host $host` diretamente no alias do NPM. O build candidato passou o teste unitário, mas a instalação foi corretamente rejeitada pelos gates operacionais:

1. o primeiro canário detectou drift de renderer esperado;
2. após normalização controlada, o smoke público mostrou 404 porque o publication-gateway usa o Host numérico para selecionar `cloudif-p<numero>-active-web`.

O instalador fez rollback automático e o Publisher live permaneceu v17. Nenhum binário candidato v18 foi ativado.

A cadeia correta é:

```text
Browser Host/Origin: agendaunica.cloudiff.duckdns.org
        ↓
NPM: Host 1020.cloudiff.duckdns.org (roteamento interno)
     X-Forwarded-Host agendaunica.cloudiff.duckdns.org (identidade pública)
        ↓
publication-gateway: escolhe backend pelo Host numérico,
                     valida X-Forwarded-Host *.cloudiff.duckdns.org,
                     entrega Host/X-Forwarded-Host públicos à bridge
        ↓
web/api: recebe Host agendaunica.cloudiff.duckdns.org
```

O gateway ganhou `map $http_x_forwarded_host $cloudif_public_host` com fallback para `$host` e somente aceita forwarded host no domínio CloudIFF. Assim o roteamento interno continua determinístico e a aplicação volta a enxergar mesma origem.

Depois dessa correção o Publisher v17 regenerou o Nginx no formato numérico normal. Os três endpoints (`agendaunica`, `1020` e P10 versionada) retornaram health 200; testes de login com credencial deliberadamente inválida retornaram 401 nos três Origins, provando que não existe mais bloqueio CSRF por origem.

Os diretórios de candidato v18 rejeitado permanecem apenas como evidência/staging e não são symlinks live; não foram apagados por política PGH de não realizar exclusão de árvore sem autorização explícita.
