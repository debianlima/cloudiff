# Auditoria CloudIFF — silvipro (1002)

Data: 22/11/2026. Classificação: **PARCIAL_PRODUCAO_LEGADA_PLACEHOLDER**.

## Referência obrigatória

- `docs/PADRAO-CLOUDIFF-PREVIEW-HOMOLOGACAO-PRODUCAO-20261120.md`
- `docs/RUNBOOK-PADRAO-CLOUDIFF-WHP-CONTINUIDADE.md`
- `docs/FLUXO-WHP-PUBLICACAO.md`
- `docs/AGENDA-P1020-PROCEDIMENTO-GERENCIAMENTO-PUBLICACOES.md`

## Estado observado

- Integração: `ready`; Forgejo `done_via_forja_agent`; Komodo `done_via_komodo_agent`; Supabase `done`.
- Preview: `W1`, URL `https://1002-w1-preview.cloudiff.duckdns.org/`, health do read-model `True`, runtime `generic-preview`.
- Homologação atual: nenhuma candidata ativa.
- Produção ativa: `P1`, URL `https://1002-p1-publication.cloudiff.duckdns.org/`, runtime online `True`, healthy `True`.
- Histórico operacional: 0 versão(ões) no read-model atual.
- Alias(es): `silvipro.cloudiff.duckdns.org`.

## Navegação real no readiness

- alias: `https://silvipro.cloudiff.duckdns.org/` → **silvipro · primeiros passos**.
- preview: `https://1002-w1-preview.cloudiff.duckdns.org/` → **silvipro · primeiros passos**.
- production: `https://1002-p1-publication.cloudiff.duckdns.org/` → **silvipro · primeiros passos**.
- stable: `https://1002.cloudiff.duckdns.org/` → **silvipro · primeiros passos**.

## Adequação necessária

Transporte W/P funciona, mas a aplicação ainda serve a página de primeiros passos. Corrigir código-fonte e migrar P1 legada no próximo ciclo H→P humano.

## Gates

- Não criar H/P automaticamente para resolver drift de catálogo ou conteúdo.
- Provar runtime real antes de mostrar Online/Offline.
- Preservar número/URL do Preview existente.
- Próxima Produção moderna deve promover a mesma instância homologada.
- Produção substituída só pode ser declarada Offline após prova `inactive|removed` no Executor.
- Registrar prestate, rollback, evidência e atualizar esta auditoria após remediação.
