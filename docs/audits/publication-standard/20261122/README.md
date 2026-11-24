# Auditorias de adequação ao padrão W→H→P — 22/11/2026

Projetos auditados: **25**.

Todas as auditorias desta pasta referenciam o mesmo contrato global e devem ser relidas antes de alterar o respectivo projeto.

## Contagem por classificação

- `ATIVO_TESTE_HARDNESS`: 1
- `BLOQUEADO_RUNTIME_COMPOSTO_STABLE_502`: 1
- `CONFORME_REFERENCIA`: 1
- `DEGRADADO_INTEGRACAO`: 1
- `LEGADO_NAO_PROVISIONADO`: 2
- `LEGADO_TESTE_NAO_PROVISIONADO`: 7
- `PARCIAL_PRODUCAO_LEGADA`: 2
- `PARCIAL_PRODUCAO_LEGADA_PLACEHOLDER`: 2
- `PREVIEW_LEGADO_PLACEHOLDER`: 4
- `PREVIEW_SOURCE_LINKED_SEM_PRODUCAO`: 1
- `QUEBRADO_PREVIEW_502`: 2
- `REGISTRO_INFRA_NAO_PROVISIONADO`: 1

## Projetos

- 1001 — [`laboratorio-de-hardware`](laboratorio-de-hardware.md) — `PARCIAL_PRODUCAO_LEGADA`
- 1002 — [`silvipro`](silvipro.md) — `PARCIAL_PRODUCAO_LEGADA_PLACEHOLDER`
- 1003 — [`silvipro2`](silvipro2.md) — `LEGADO_NAO_PROVISIONADO`
- 1004 — [`lima-teste`](lima-teste.md) — `LEGADO_TESTE_NAO_PROVISIONADO`
- 1005 — [`teste-lima`](teste-lima.md) — `LEGADO_TESTE_NAO_PROVISIONADO`
- 1006 — [`lima-teste-3`](lima-teste-3.md) — `LEGADO_TESTE_NAO_PROVISIONADO`
- 1007 — [`silvipro-jt-2026`](silvipro-jt-2026.md) — `PREVIEW_LEGADO_PLACEHOLDER`
- 1008 — [`teste`](teste.md) — `LEGADO_TESTE_NAO_PROVISIONADO`
- 1010 — [`teste-sofa`](teste-sofa.md) — `PREVIEW_LEGADO_PLACEHOLDER`
- 1011 — [`tuleap-laboratorio-de-hardware`](tuleap-laboratorio-de-hardware.md) — `LEGADO_NAO_PROVISIONADO`
- 1014 — [`grupix`](grupix.md) — `QUEBRADO_PREVIEW_502`
- 1015 — [`teste-4`](teste-4.md) — `LEGADO_TESTE_NAO_PROVISIONADO`
- 1016 — [`teste-3`](teste-3.md) — `LEGADO_TESTE_NAO_PROVISIONADO`
- 1017 — [`teste-5`](teste-5.md) — `LEGADO_TESTE_NAO_PROVISIONADO`
- 1018 — [`testando123`](testando123.md) — `QUEBRADO_PREVIEW_502`
- 1019 — [`hardness-e2e-0254`](hardness-e2e-0254.md) — `ATIVO_TESTE_HARDNESS`
- 1020 — [`agenda-unica`](agenda-unica.md) — `CONFORME_REFERENCIA`
- 1021 — [`cpuhub`](cpuhub.md) — `PARCIAL_PRODUCAO_LEGADA`
- 1022 — [`cadales`](cadales.md) — `PARCIAL_PRODUCAO_LEGADA_PLACEHOLDER`
- 1023 — [`isha`](isha.md) — `PREVIEW_LEGADO_PLACEHOLDER`
- 1024 — [`mvplanner`](mvplanner.md) — `PREVIEW_LEGADO_PLACEHOLDER`
- 1025 — [`paperclip`](paperclip.md) — `BLOQUEADO_RUNTIME_COMPOSTO_STABLE_502`
- 1026 — [`sgrep-v2`](sgrep-v2.md) — `PREVIEW_SOURCE_LINKED_SEM_PRODUCAO`
- 1027 — [`msha`](msha.md) — `DEGRADADO_INTEGRACAO`
- 1028 — [`pghd-contexto`](pghd-contexto.md) — `REGISTRO_INFRA_NAO_PROVISIONADO`

## Índice/read-model obrigatório — 22/11/2026

O caminho quente da interface é o SQLite `/var/lib/cloudif/portal/cloudif-portal-readmodel.db`; não varrer Docker/filesystem/Komodo para renderizar listas. Mutação em provisionamento, ambiente, W/H/P, histórico, rollback, exclusão, Conectores ou Aprovações deve invalidar/atualizar o índice no próprio fluxo e disparar refresh em background. Leitura usa stale-while-revalidate. O refresh global é rede de segurança a cada 5 minutos; a auditoria completa roda 03:20 `America/Sao_Paulo` e nunca muta runtime. Norma: `docs/PADRAO-CLOUDIFF-INDICE-READMODEL-PORTAL-20261122.md`.

## Ferramentas de runtime por estágio — 23/11/2026

Norma: `docs/PADRAO-CLOUDIFF-FERRAMENTAS-RUNTIME-ESTAGIO-20261123.md`.

PHP, Node.js e Terminal devem resolver o mesmo `project + stageCode + runtime identity` selecionado; não derivar `api/web/app` por convenção, não copiar Wn de outro projeto e não recriar URL/container para diagnóstico. Preview linked-compose usa stack real; H/P Compose usam `services/routes` do Executor; Preview composto usa par numerado app/web; P legada usa container versionado exato. Ausência de PHP/Node é `available=false`, não erro. Terminal nunca contorna ACL.

## Fechamento de padronização — 23/11/2026

Fechamento canônico: 9 projetos atuais, 16 números reservados de projetos excluídos, auditoria noturna 0 issues. Evidência: `docs/audits/FINAL-PADRONIZACAO-PROJETOS-20261123.json`.
