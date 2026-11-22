# Agenda Única P1020 — exclusão final do legado P2 e verificação física do histórico

Data: 22/11/2026.

## Situação encontrada

Após a indexação do Histórico, P2 ainda aparecia como Offline porque o Portal só permitia `Excluir container` para runtimes `compose-snapshot` reidratáveis.

P2 era legado:

- `cloudif-p1020-p2-publication-web` existia, porém estava `Exited`;
- não possuía volume Docker;
- `stage_production_releases` registrava P2 como `ready`, `is_active=0`;
- não existia stage/rota P2 no Publisher;
- a imagem registrada `sha256:95b97...` já não existia no Docker.

Logo, o botão `Subir` dava uma expectativa de reidratação que não era verdadeira.

## Contrato corrigido

P histórica inativa pode ser excluída em dois modos:

1. `compose-snapshot`: remove runtime, preserva snapshot e auditoria;
2. `legacy-final`: Komodo valida projeto, número P, container, labels e ausência do alias ativo; remove o container e marca o runtime Komodo como `deleted`. Não há reidratação automática.

A Produção ativa continua protegida e nunca pode ser excluída por essa ação.

O Portal marca `project_publications` e `production_releases` como `archived`, portanto a versão sai imediatamente do histórico operacional e permanece somente na trilha de auditoria.

## Execução P2

Backups:

- Portal: `/var/lib/cloudif/portal/backups/agenda-p2-final-delete-20261122T152856Z`
- Forja: `/srv/cloudif/backups/agenda-p2-final-delete-20261122T152914Z`

Resultado:

- endpoint Komodo: HTTP 200;
- `containersRemoved=1`;
- `volumesRemoved=0`;
- `imagePreserved=false` porque a imagem já estava ausente antes da exclusão;
- `canRehydrate=false`;
- P2 marcada `archived` no Portal.

## Verificação física final

Containers históricos específicos:

- `cloudif-p1020-p2-publication-web`: ABSENT;
- `cloudif-p1020-p3-publication-web`: ABSENT;
- `cloudif-p1020-p6-publication-web`: ABSENT;
- `cloudif-p1020-p7-publication-web`: ABSENT.

Deployments Compose históricos:

- P3 `dep_23d8e626...`: nenhum container; status Executor `removed`;
- P6 `dep_6523ed270...`: nenhum container; status Executor `removed`;
- P7 `dep_19bc037d0...`: nenhum container; status Executor `removed`.

Nenhum volume Docker com vínculo a esses deployments foi encontrado.

Publisher P1020 mantém somente:

- `1020-w3-preview`;
- `1020-p8-publication`.

As duas listas operacionais do Portal (`release_flow_status()` e `_rows()`) retornam somente P8.

## Produção atual

- H8 → P8;
- commit `18416127cdf9255cbb61cb4085fe983f97c902e8`;
- P8 usa `dep_4e175797c8b1ed100b2207c0`, o mesmo deployment homologado registrado no detalhe de Produção;
- `agendaunica.cloudiff.duckdns.org/api/health` continua saudável na revisão `18416127cdf9`.
