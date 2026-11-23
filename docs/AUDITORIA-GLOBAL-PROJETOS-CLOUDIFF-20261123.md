# Auditoria global dos projetos CloudIFF — 23/11/2026

## Escopo

Consolidação final do inventário do Portal, números públicos reservados, runtime W/H/P, ferramentas PHP/Node/Terminal, read-model e resíduos de exclusão.

## Classificação canônica

A existência de uma linha em `project_public_ids` **não significa que o projeto ainda exista**. O número público é preservado após exclusão para impedir reutilização acidental e manter rastreabilidade.

Estados canônicos:

- `current`: existe linha em `projects`; pode possuir runtime, integração e ACL;
- `reserved-deleted`: não existe linha em `projects`; o número público permanece reservado e não autoriza provisionamento, Preview, Terminal, PHP/Node ou publicação;
- `draft-no-runtime`: projeto atual deliberadamente sem aplicação executável/Preview;
- `current-runtime`: projeto atual com Preview/integração operacional.

## Projetos atuais

| Nº | Projeto | Estado consolidado |
|---:|---|---|
| 1001 | laboratorio-de-hardware | current-runtime; W1/P14 padronizados |
| 1002 | silvipro | current-runtime; W1 e Produção legada P1 |
| 1020 | agenda-unica | current-runtime; W3 específico do projeto e Produção moderna |
| 1021 | cpuhub | current-runtime; W1 e Produção legada P5 |
| 1022 | cadales | current-runtime; W1 e Produção legada P2 |
| 1025 | paperclip | current-runtime; W1 composto; H bloqueada por manifest composto |
| 1026 | sgrep-v2 | current-runtime source-linked W1; H/P dependem do contrato source/data |
| 1027 | msha | draft; repositório sem `docker-compose.yml` de aplicação e sem Preview; tenant Supabase existente é camada separada |
| 1028 | pghd-contexto | draft-no-runtime; agregador/documentação, sem aplicação executável configurada |

## Números reservados de projetos excluídos

Os 16 registros abaixo não são projetos atuais e não devem ser “recuperados” apenas porque possuem número público:

| Nº | Slug |
|---:|---|
| 1003 | silvipro2 |
| 1004 | lima-teste |
| 1005 | teste-lima |
| 1006 | lima-teste-3 |
| 1007 | silvipro-jt-2026 |
| 1008 | teste |
| 1010 | teste-sofa |
| 1011 | tuleap-laboratorio-de-hardware |
| 1014 | grupix |
| 1015 | teste-4 |
| 1016 | teste-3 |
| 1017 | teste-5 |
| 1018 | testando123 |
| 1019 | hardness-e2e-0254 |
| 1023 | isha |
| 1024 | mvplanner |

A evidência histórica de exclusão em `/srv/cloudif/admin-project-deletions/` confirma que os projetos foram removidos deliberadamente e que o número público foi preservado.

## Resíduo encontrado e corrigido

Durante a auditoria, cinco projetos `reserved-deleted` possuíam Preview W1 residual criado posteriormente por rotina de recuperação antiga:

- 1007 `silvipro-jt-2026`;
- 1010 `teste-sofa`;
- 1019 `hardness-e2e-0254`;
- 1023 `isha`;
- 1024 `mvplanner`.

Esses containers não possuíam volume Docker próprio de aplicação; montavam checkouts históricos e arquivos de runtime de stage. Foram removidos pelo fluxo oficial de exclusão/reconciliação, preservando os números públicos. Antes da limpeza foram gerados `git bundle` restritos em backup, sem duplicar credenciais do `.git/config`.

Regra: **nunca recriar Preview de `reserved-deleted`**. Runtime recovery exige linha atual em `projects` e autorização correspondente.

## Correções permanentes

1. O read-model `projects/public-catalog` lista apenas projetos atuais (`project_public_ids JOIN projects`).
2. Reservas ficam em `projects/reserved-public-numbers` com `lifecycle=reserved-deleted`.
3. A auditoria noturna compara o catálogo apenas com projetos atuais.
4. A auditoria registra `reserved-deleted-operational-residue` quando uma reserva reaparece em tabelas operacionais.
5. A auditoria consulta em modo somente leitura o status de Preview para reservas e registra `reserved-deleted-preview-runtime` se surgir runtime residual.
6. `/unpublish` deve remover Produção/aliases **e todos os stages W/H/P** ligados ao mesmo `public_number`, preservando certificados para auditoria/rollback.
7. `ensure_preview`/`recreate_preview`/status de provisionamento continuam exigindo linha atual em `projects`; número reservado isolado nunca autoriza mutação.

## MSHA

O MSHA é projeto atual, mas não possui aplicação pronta para W1. O repositório contém apenas documentação inicial e o stack Komodo declara `docker-compose.yml` ausente. Portanto não foi criado Preview artificial.

O tenant Supabase `iff3546365-msha` é independente da aplicação. A reconciliação de 23/11/2026 completou os serviços previstos do tenant existente: DB, Auth, Studio, Kong, Meta, Realtime, Storage e Supavisor ficaram saudáveis; Functions ficou running. Nenhum volume foi apagado e o banco não foi resetado. Essa camada permanece separada do lifecycle W/H/P da aplicação.

## PGHD Contexto

`pghd-contexto` é deliberadamente `draft-no-runtime`. Não deve receber W/H/P até que exista repositório/aplicação declarada por contrato.

## Regra operacional para agentes

Antes de qualquer recuperação/provisionamento:

```text
project_public_ids existe?
       ↓
projects existe?
  não → reserved-deleted → NÃO provisionar
  sim → validar owner/ACL/integração → operar o estágio real
```

Nunca usar `project_public_ids` como catálogo de projetos ativos.

## Referências

- `docs/PADRAO-CLOUDIFF-FERRAMENTAS-RUNTIME-ESTAGIO-20261123.md`
- `docs/PADRAO-CLOUDIFF-INDICE-READMODEL-PORTAL-20261122.md`
- `docs/RUNBOOK-PADRAO-CLOUDIFF-WHP-CONTINUIDADE.md`
- `docs/AUDITORIA-GLOBAL-PROJETOS-WHP-20261122.md`
