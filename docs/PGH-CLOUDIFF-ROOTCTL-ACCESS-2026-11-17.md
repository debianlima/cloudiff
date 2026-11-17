# CloudIFF — acesso SSH delegado e diagnóstico do atualizador

Observações verificadas em 17/11/2026 às 18h50–19h00 UTC,
pelo conector PGH LabIFF, com identidade cti em SSH preexistente.

O script scripts/cloudiff-four-hosts-readonly-check.sh usa os
wrappers do LabIFF para consultar SOMENTE o comando status do
cloudiff-rootctl permitido no sudoers. Não executa mudanças,
não carrega credenciais, não lê arquivos privados e não
substitui revisão de G0–G5.

| Host | SSH cti | rootctl delegado | Estado observado |
| --- | --- | --- | --- |
| Forja 10.62.91.2 | Sim | status, preflight | 5 hashes OK; 2 health HTTP200 |
| Hospedagem 10.62.92.7 | Sim | status, preflight | 3 hashes OK; 2 health HTTP200 |
| Maurício 10.62.91.3 | Sim | status, inspect | degraded; updater assinado failed exit22 |
| Faro 10.62.91.5 | Sim | status, inspect | degraded; updater assinado exit22; fwupd-refresh failed |

O script não pede senha, não utiliza shell root irrestrito
e depende dos wrappers oficiais previamente autorizados.
As restrições de cada host diferem. O rootctl possui uma
ação cutover-v1451 nos hosts selecionados, mas NÃO deve
ser executada antes dos testes de backup, restauração,
OpenBao produtivo, Docker Hn→Pn, revogação Git e auditoria.

## Falha de atualização assinado

Nos hosts Maurício e Faro o serviço
cloudiff-v2-agent-updater.service apresentou exit22 e
HTTP404 ao recuperar manifesto; em seguida ocorreu
JSONDecodeError. O artefato de código instalado equivale
ao deploy/agent_updater.sh do repositório, SHA256:
d38b8fce733d3d85bc2e2c4d0aad99f3df8c8043da8c57fdb2ee049a302c1963.

O update usa HTTPS com certificado de cliente para a
rota cloudiff.duckdns.org/__cloudiff_agent_updates/stable/
manifest.json e manifesto de assinatura. Um HEAD sem
certificado retornou 403, o que não prova indisponibilidade
no fluxo mTLS. Diagnosticar o publicador de manifests e
rota NPM/proxy com proprietário autenticado. **Não** remover
verificação de assinatura nem ignorar certificado CA para
fazer o serviço passar.

## Contas e cofre

As contas históricas cloudif-agent (usuário técnico Komodo)
e cloudif-bot (Git Provider Forgejo) precisam de confirmação
por API administrativa; não são o usuário Linux cti.
svc-pgh-cloudiff segue pendente de criação; não duplicar.
OpenBao homologação IFF2 saudável não equivale a cofre
produtivo. Ver guia de identidades PGH e credenciais.
O histórico Git P0 root-owned ainda exige remediação por
owner com backup/rollback. Nenhum secret_ref foi criado.

## Prova de execução e limites

A verificação read-only foi executada nos quatro servidores
e reproduziu os estados acima. O script e este documento
não concedem privilégios adicionais. Confirmação produtiva
requer identidade legítima, lock, verificação de owner,
backup/rollback e testes negativos sob G0–G5.
