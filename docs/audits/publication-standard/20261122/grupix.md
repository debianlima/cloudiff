# Auditoria CloudIFF — grupix (1014)

Data: 22/11/2026. Classificação: **QUEBRADO_PREVIEW_502**.

## Referência obrigatória

- `docs/PADRAO-CLOUDIFF-PREVIEW-HOMOLOGACAO-PRODUCAO-20261120.md`
- `docs/RUNBOOK-PADRAO-CLOUDIFF-WHP-CONTINUIDADE.md`
- `docs/FLUXO-WHP-PUBLICACAO.md`
- `docs/AGENDA-P1020-PROCEDIMENTO-GERENCIAMENTO-PUBLICACOES.md`

## Estado observado

- Integração moderna: não cadastrada.
- Preview: `W1`, URL `https://1014-w1-preview.cloudiff.duckdns.org/`, health do read-model `False`, runtime `None`.
- Homologação atual: nenhuma candidata ativa.
- Produção ativa moderna: nenhuma.
- Histórico operacional: 0 versão(ões) no read-model atual.

## Navegação real no readiness

- preview: `https://1014-w1-preview.cloudiff.duckdns.org/` → **502**.
- stable: `https://1014.cloudiff.duckdns.org/` → **Authentik/Portal**.

## Adequação necessária

W1 existe mas navegador confirma 502. Descobrir ownership/runtime real e reconciliar bridge/upstream antes de H/P.

## Gates

- Não criar H/P automaticamente para resolver drift de catálogo ou conteúdo.
- Provar runtime real antes de mostrar Online/Offline.
- Preservar número/URL do Preview existente.
- Próxima Produção moderna deve promover a mesma instância homologada.
- Produção substituída só pode ser declarada Offline após prova `inactive|removed` no Executor.
- Registrar prestate, rollback, evidência e atualizar esta auditoria após remediação.
## Remediação executada nesta auditoria

- Dois deployments H órfãos (`dep_832e4c338875edfe6ccaef3c` e `dep_1bc1b35430c82babff01d9af`) estavam marcados `running` sem containers/candidatas. Ambos foram reconciliados para `inactive`.
- Rotas H1/H2/H3 e W2 antigas foram removidas do Publisher com certificados preservados.
- W1 foi mantido e continua 502; a correção do Preview exige descoberta do runtime/ownership, não criação cega de recursos.
