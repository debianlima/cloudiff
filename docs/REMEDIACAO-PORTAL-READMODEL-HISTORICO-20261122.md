# Portal CloudIFF — read-model indexado e exclusão real do Histórico operacional

Data: 22/11/2026. Projeto de referência: `agenda-unica` P1020.

## Problema observado

A UI possuía duas fontes de renderização para Publicações:

- a página principal (`Alternar entre Publicações`) lia `_rows(slug)`;
- o modal (`Histórico de Produção`) lia `release_flow_status()`.

`Excluir container` removia o runtime e gravava `runtimeDeletedAt`, mas mantinha `production_releases.status='published'` e `project_publications.status='published'`. Assim Pn continuava aparecendo em ambas as listas, com estado `Containers excluídos` e novos botões de ação.

Além disso, enriquecimentos de Projetos/Publicações ainda executavam leitura de job em filesystem e consultas a Komodo/serviços remotos durante o render. Conectores e Aprovações também consultavam seus serviços a cada carregamento.

## Semântica corrigida de `Excluir`

A exclusão de uma P histórica agora é uma transição operacional. Compose-snapshot preserva snapshot; legado inativo pode ser removido em modo final validado pelo Komodo:

1. remove runtime/bridge/stage conforme o contrato já existente;
2. preserva snapshot, `detail_json` e dados de auditoria;
3. marca `production_releases.status='archived'` e `project_publications.status='archived'`;
4. remove a P da lista operacional imediatamente;
5. ela não recebe mais `Subir`, `Ativar` ou `Excluir` na interface;
6. a auditoria interna continua disponível no banco/evidência.

`release_flow_status()` e `_rows()` exibem somente publicações canônicas `status='published'`.

No Agenda, P6/P3 foram reconciliadas para `archived`; depois P7 também foi excluída pelo fluxo humano e P2 foi removida em `legacy-final`. O histórico operacional agora contém somente P8 ativa; P2/P3/P6/P7 permanecem apenas como auditoria arquivada.

Backup da reconciliação P6/P3:
`/var/lib/cloudif/portal/backups/agenda-archive-deleted-history-20261122T143345Z`.

## Índice persistente

Foi criado `cloudif_portal_readmodel.py`, com tabela descartável:

`portal_readmodel_cache(namespace, cache_key, payload_json, source_version, updated_at)`.

O índice **não é fonte de verdade**. Ele pode ser apagado/reconstruído. Fontes canônicas continuam sendo Portal DB, Komodo/Forja, serviços de Approval/Onboarding e runtime real.

Namespaces usados:

- `projects/discovered`;
- `tenants/registry`;
- `project-job-state/<slug>`;
- `project-runtime-state/<slug>`;
- `project-runtime-job/<slug>`;
- `publication-project-context/<slug>|<framework>`;
- `connectors/all`;
- `approvals/rows` e `approvals/policies`.

## Atualização e invalidação

O timer existente `cloudif-portal-refresh-cache.timer` continua como único agendador e roda a cada 60 s. O serviço oneshot foi estendido para pré-aquecer os read-models em background.

Mutações invalidam a chave/namespace afetado e disparam o mesmo serviço com `systemctl --no-block`:

- criar/editar/sincronizar projeto;
- criar/rotacionar/reconciliar conector;
- aprovar/rejeitar/revogar aprovação;
- excluir publicação histórica.

Assim o clique do usuário lê SQLite na maior parte do tempo; filesystem e chamadas remotas ficam fora do caminho quente.

## Performance medida

Antes do pré-aquecimento, após invalidar o contexto da Agenda:

- primeira leitura: ~970,48 ms;
- segunda leitura indexada: ~1,43 ms.

Depois de habilitar o pré-aquecimento pelo timer:

- primeira leitura observada no request: ~1,89 ms;
- segunda leitura: ~1,41 ms.

O refresh background dos nove projetos levou ~20 s de wall clock numa execução observada, mas apenas ~506 ms de CPU; isso não bloqueia o request do usuário.

## Estado final do Agenda

Lista operacional comum às duas telas:

- P8 — ativa.

P2/P3/P6/P7 permanecem somente como registros `archived` para auditoria. Nenhum desses históricos possui container/volume ativo no host.

P8 e `agendaunica.cloudiff.duckdns.org` continuaram saudáveis, revisão `18416127cdf9`.

## Backups live

- `/var/lib/cloudif/portal/backups/readmodel-index-20261122T143221Z`
- `/var/lib/cloudif/portal/backups/readmodel-prewarm-20261122T143606Z`
- `/var/lib/cloudif/portal/backups/agenda-archive-deleted-history-20261122T143345Z`
