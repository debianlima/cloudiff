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
