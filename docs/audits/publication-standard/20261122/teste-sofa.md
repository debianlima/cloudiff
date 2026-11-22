# Auditoria CloudIFF — teste-sofa (1010)

Data: 22/11/2026. Classificação: **PREVIEW_LEGADO_PLACEHOLDER**.

## Referência obrigatória

- `docs/PADRAO-CLOUDIFF-PREVIEW-HOMOLOGACAO-PRODUCAO-20261120.md`
- `docs/RUNBOOK-PADRAO-CLOUDIFF-WHP-CONTINUIDADE.md`
- `docs/FLUXO-WHP-PUBLICACAO.md`
- `docs/AGENDA-P1020-PROCEDIMENTO-GERENCIAMENTO-PUBLICACOES.md`

## Estado observado

- Integração moderna: não cadastrada.
- Preview: `W1`, URL `https://1010-w1-preview.cloudiff.duckdns.org/`, health do read-model `False`, runtime `None`.
- Homologação atual: nenhuma candidata ativa.
- Produção ativa moderna: nenhuma.
- Histórico operacional: 0 versão(ões) no read-model atual.

## Navegação real no readiness

- preview: `https://1010-w1-preview.cloudiff.duckdns.org/` → **teste-sofa · primeiros passos**.
- stable: `https://1010.cloudiff.duckdns.org/` → **Authentik/Portal**.

## Adequação necessária

Preview responde com primeiros passos, sem integração moderna. Confirmar proprietário/finalidade e integrar antes de H/P.

## Gates

- Não criar H/P automaticamente para resolver drift de catálogo ou conteúdo.
- Provar runtime real antes de mostrar Online/Offline.
- Preservar número/URL do Preview existente.
- Próxima Produção moderna deve promover a mesma instância homologada.
- Produção substituída só pode ser declarada Offline após prova `inactive|removed` no Executor.
- Registrar prestate, rollback, evidência e atualizar esta auditoria após remediação.
