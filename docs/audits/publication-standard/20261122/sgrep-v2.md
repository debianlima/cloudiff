# Auditoria CloudIFF — sgrep-v2 (1026)

Data: 22/11/2026. Classificação: **PREVIEW_SOURCE_LINKED_SEM_PRODUCAO**.

## Referência obrigatória

- `docs/PADRAO-CLOUDIFF-PREVIEW-HOMOLOGACAO-PRODUCAO-20261120.md`
- `docs/RUNBOOK-PADRAO-CLOUDIFF-WHP-CONTINUIDADE.md`
- `docs/FLUXO-WHP-PUBLICACAO.md`
- `docs/AGENDA-P1020-PROCEDIMENTO-GERENCIAMENTO-PUBLICACOES.md`

## Estado observado

- Integração: `adopted_existing_staging`; Forgejo `adopted_verified`; Komodo `adopted_verified`; Supabase `not_provisioned`.
- Preview: `W1`, URL `https://1026-w1-preview.cloudiff.duckdns.org/`, health do read-model `True`, runtime `source-linked-preview`.
- Homologação atual: nenhuma candidata ativa.
- Produção ativa moderna: nenhuma.
- Histórico operacional: 0 versão(ões) no read-model atual.

## Navegação real no readiness

- preview: `https://1026-w1-preview.cloudiff.duckdns.org/` → **SGREP - Fine Comp**.
- stable: `https://1026.cloudiff.duckdns.org/` → **Authentik/Portal**.

## Adequação necessária

W1 source-linked está saudável. Formalizar contrato H/P que preserve separação fonte/dados antes de qualquer Produção.

## Gates

- Não criar H/P automaticamente para resolver drift de catálogo ou conteúdo.
- Provar runtime real antes de mostrar Online/Offline.
- Preservar número/URL do Preview existente.
- Próxima Produção moderna deve promover a mesma instância homologada.
- Produção substituída só pode ser declarada Offline após prova `inactive|removed` no Executor.
- Registrar prestate, rollback, evidência e atualizar esta auditoria após remediação.

## Índice/read-model obrigatório — 22/11/2026

O caminho quente da interface é o SQLite `/var/lib/cloudif/portal/cloudif-portal-readmodel.db`; não varrer Docker/filesystem/Komodo para renderizar listas. Mutação em provisionamento, ambiente, W/H/P, histórico, rollback, exclusão, Conectores ou Aprovações deve invalidar/atualizar o índice no próprio fluxo e disparar refresh em background. Leitura usa stale-while-revalidate. O refresh global é rede de segurança a cada 5 minutos; a auditoria completa roda 03:20 `America/Sao_Paulo` e nunca muta runtime. Norma: `docs/PADRAO-CLOUDIFF-INDICE-READMODEL-PORTAL-20261122.md`.

## Ferramentas de runtime por estágio — 23/11/2026

Norma: `docs/PADRAO-CLOUDIFF-FERRAMENTAS-RUNTIME-ESTAGIO-20261123.md`.

PHP, Node.js e Terminal devem resolver o mesmo `project + stageCode + runtime identity` selecionado; não derivar `api/web/app` por convenção, não copiar Wn de outro projeto e não recriar URL/container para diagnóstico. Preview linked-compose usa stack real; H/P Compose usam `services/routes` do Executor; Preview composto usa par numerado app/web; P legada usa container versionado exato. Ausência de PHP/Node é `available=false`, não erro. Terminal nunca contorna ACL.
## Prova runtime tools — 23/11/2026

Preview source-linked W1 passou PHP/Node/Terminal usando a identidade source-linked existente. Não criar H/P sem contrato source/data já documentado.

## Homologação pelo runtime real — 23/11/2026

SGREP v2 W1 passou no preflight completo com `app + db + sat`; aliases `preview-db` e `preview-sat`, volume PostgreSQL e binds autorizados são preservados no snapshot/restauração. Nenhuma H foi criada pela auditoria.
