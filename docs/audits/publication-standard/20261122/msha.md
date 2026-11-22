# Auditoria CloudIFF — msha (1027)

Data: 22/11/2026. Classificação: **DEGRADADO_INTEGRACAO**.

## Referência obrigatória

- `docs/PADRAO-CLOUDIFF-PREVIEW-HOMOLOGACAO-PRODUCAO-20261120.md`
- `docs/RUNBOOK-PADRAO-CLOUDIFF-WHP-CONTINUIDADE.md`
- `docs/FLUXO-WHP-PUBLICACAO.md`
- `docs/AGENDA-P1020-PROCEDIMENTO-GERENCIAMENTO-PUBLICACOES.md`

## Estado observado

- Integração: `degraded`; Forgejo `done_via_forja_agent`; Komodo `done_via_komodo_agent`; Supabase `tenant_runtime_error`.
- Preview: não configurado no modelo atual.
- Homologação atual: nenhuma candidata ativa.
- Produção ativa moderna: nenhuma.
- Histórico operacional: 0 versão(ões) no read-model atual.

## Navegação real no readiness

- stable: `https://1027.cloudiff.duckdns.org/` → **Authentik/Portal**.

## Adequação necessária

Integração está degradada por tenant runtime/Supabase e não há Preview. Corrigir a integração primeiro e só depois criar o Preview fixo no padrão atual.

## Gates

- Não criar H/P automaticamente para resolver drift de catálogo ou conteúdo.
- Provar runtime real antes de mostrar Online/Offline.
- Preservar número/URL do Preview existente.
- Próxima Produção moderna deve promover a mesma instância homologada.
- Produção substituída só pode ser declarada Offline após prova `inactive|removed` no Executor.
- Registrar prestate, rollback, evidência e atualizar esta auditoria após remediação.
