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

## Índice/read-model obrigatório — 22/11/2026

O caminho quente da interface é o SQLite `/var/lib/cloudif/portal/cloudif-portal-readmodel.db`; não varrer Docker/filesystem/Komodo para renderizar listas. Mutação em provisionamento, ambiente, W/H/P, histórico, rollback, exclusão, Conectores ou Aprovações deve invalidar/atualizar o índice no próprio fluxo e disparar refresh em background. Leitura usa stale-while-revalidate. O refresh global é rede de segurança a cada 5 minutos; a auditoria completa roda 03:20 `America/Sao_Paulo` e nunca muta runtime. Norma: `docs/PADRAO-CLOUDIFF-INDICE-READMODEL-PORTAL-20261122.md`.

## Ferramentas de runtime por estágio — 23/11/2026

Norma: `docs/PADRAO-CLOUDIFF-FERRAMENTAS-RUNTIME-ESTAGIO-20261123.md`.

PHP, Node.js e Terminal devem resolver o mesmo `project + stageCode + runtime identity` selecionado; não derivar `api/web/app` por convenção, não copiar Wn de outro projeto e não recriar URL/container para diagnóstico. Preview linked-compose usa stack real; H/P Compose usam `services/routes` do Executor; Preview composto usa par numerado app/web; P legada usa container versionado exato. Ausência de PHP/Node é `available=false`, não erro. Terminal nunca contorna ACL.

## Ferramentas de runtime — legado sem ACL moderna — 23/11/2026

Este registro não possui linha moderna suficiente em `projects`/ACL para autorizar PHP/Node/Terminal pelo contrato atual. Não contornar `_project_allowed()` e não criar ownership implícito. A migração exige confirmar responsável/finalidade e reconciliar o projeto moderno antes de habilitar Terminal.

## Classificação final — reserved-deleted — 23/11/2026

Este slug **não é projeto atual**. O registro `1014` existe somente em `project_public_ids` para preservar o número público após exclusão. Não criar Preview/H/P, não abrir Terminal e não reconstruir ACL a partir deste registro isolado. Uma recriação futura deve ser um novo onboarding humano explícito, preservando o histórico deste número.
