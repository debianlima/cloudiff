# CloudIFF — padrão de índice/read-model do Portal

Data de consolidação: 22/11/2026.

## Objetivo

O Portal deve responder rapidamente ao usuário sem vasculhar diretórios, containers, Docker, Komodo, Forgejo ou arquivos de provisionamento a cada abertura de aba/projeto.

O padrão é **DB-first para leitura da interface**:

```text
fontes canônicas / runtime real
        ↓ mutação ou refresh em background
cloudif-portal-readmodel.db (SQLite)
        ↓ leitura rápida
Portal: Projetos / Publicações / Conectores / Aprovações
```

O arquivo de índice não é a autoridade. A autoridade continua sendo o banco canônico do Portal, os serviços especializados e o runtime real. O read-model é um índice descartável e reconstruível.

## Banco preferencial

O índice oficial é:

`/var/lib/cloudif/portal/cloudif-portal-readmodel.db`

SQLite foi escolhido no lugar de um índice JSON porque oferece:

- chave por namespace + objeto;
- atualização atômica;
- WAL e `busy_timeout`;
- invalidação pontual;
- histórico de eventos e auditorias;
- leitura concorrente rápida;
- reconstrução sem transformar o índice em fonte de verdade.

Arquivos JSON podem existir como **export, backup ou evidência**, mas não são caminho quente da interface.

## Estrutura

### `portal_readmodel_cache`

Cache materializado por `namespace/cache_key`.

Namespaces atuais incluem:

- `projects/discovered` — lista corrente exibida na aba Projetos;
- `projects/public-catalog` — catálogo dos IDs reservados/públicos, inclusive históricos;
- `publication-project-context/<slug>|...` — contexto de publicação já materializado;
- `project-runtime-state/<slug>`;
- `project-runtime-job/<slug>`;
- `project-job-state/<slug>`;
- `connectors/all`;
- `approvals/rows` e `approvals/policies`;
- `tenants/registry`;
- `audit/last-nightly`.

### `portal_readmodel_events`

Journal leve de invalidações/mutações que exigem atualização do índice. Não contém secrets.

### `portal_readmodel_audit_runs`

Histórico das reconciliações noturnas. Mantém as últimas 365 execuções.

## Regra de leitura da interface

1. Ler primeiro o SQLite do read-model.
2. Se a entrada estiver fresca, retornar imediatamente.
3. Se estiver vencida mas ainda dentro do `max_stale`, retornar o último valor conhecido e disparar refresh em background (**stale-while-revalidate**).
4. Apenas ausência completa de índice permite loader síncrono de recuperação.
5. A navegação normal do usuário **não deve** executar `docker ps`, `docker inspect`, varredura de `/srv`, leitura de centenas de jobs ou chamadas Komodo para montar a lista inicial.
6. Diagnósticos explícitos — Terminal, PHP, Node.js, inspeção de runtime, botão Atualizar diagnóstico — podem consultar a máquina porque o usuário pediu informação ao vivo.

Medições de 22/11/2026 no host do Portal:

- `projects/discovered`: ~0,28 ms por leitura do SQLite;
- `projects/public-catalog`: ~0,37 ms;
- `connectors/all`: ~0,81 ms;
- `publication-project-context/agenda-unica|`: ~0,44 ms;
- materialização da lista de Projetos: ~19 ms;
- Aprovações: cache histórico com ~6 MB/6.136 registros, leitura ~79 ms; primeiro render observado ~1,78 s e renders seguintes ~114–133 ms.

Aprovações já está DB-first e não deve voltar a consulta remota no request. A otimização de índice normalizado/paginação lazy do histórico ficou registrada como **T-046**.

## Regra de escrita: toda mutação atualiza o índice

Uma operação que muda estado visível deve, no próprio fluxo de sucesso, chamar `cloudif_portal_readmodel.project_changed(...)` ou invalidar o namespace específico e disparar refresh em background.

| Operação | Evento / invalidação mínima |
|---|---|
| Criar/editar projeto | `projects`, `connectors`, job/runtime do projeto |
| Worker de provisionamento concluiu | `project-provision-completed` + Projetos/Conectores/runtime |
| Worker de provisionamento falhou | `project-provision-failed` + estado do job/projeto |
| Excluir projeto | `project-deleted` + Projetos/Conectores/runtime |
| Reconciliar exclusão já realizada | `project-deletion-reconciled` |
| Criar/garantir Preview | `preview-ensured` |
| Criar Homologação | `homologation-created` |
| Aprovar/rejeitar H | `homologation-approved` / `homologation-rejected` |
| Promover H→P | `production-promoted` / `production-published` |
| Subir P histórica | `historical-production-started` |
| Desligar P histórica | `historical-production-stopped` |
| Excluir runtime histórico | `historical-production-deleted` |
| Rollback | `production-rollback` |
| Salvar variáveis pela UI humana | `environment-human-save` |
| Executar alteração de ambiente autorizada | `environment-change-executed` |
| Mutar Conectores | invalidar `connectors` + refresh |
| Aprovar/rejeitar/revogar aprovação | invalidar `approvals` + refresh |

Um novo provisionador, exclusor, promotor ou controlador de runtime **não está completo** se alterar estado real sem integrar o read-model.

## Atualização periódica de segurança

`cloudif-portal-refresh-cache.timer` deixou de ser o mecanismo primário de consistência. As mutações são event-driven.

O timer permanece como rede de segurança:

- `OnBootSec=30s`;
- `OnUnitActiveSec=5min`;
- executa fora do request do usuário;
- reconstrói namespaces a partir das fontes canônicas.

Essa periodicidade reduz polling desnecessário sem deixar uma mutação aguardando cinco minutos, porque a própria mutação dispara refresh.

## Auditoria noturna

Unidades:

- `cloudif-portal-readmodel-audit.service`;
- `cloudif-portal-readmodel-audit.timer`.

Agenda:

`03:20 America/Sao_Paulo`

A auditoria:

1. dispara um refresh do read-model;
2. compara `project_public_ids` com `projects/public-catalog`;
3. detecta mais de uma Produção ativa por projeto;
4. revisa `release_flow_status()` dos projetos operacionais;
5. sinaliza Preview unhealthy, P ativa offline e P histórica online;
6. grava o relatório no SQLite;
7. **não promove, não sobe, não desliga, não exclui runtime e não altera secrets**.

O serviço roda com `Nice=15`, `IOSchedulingClass=idle`, `CPUWeight=10` e `IOWeight=10`.

### Local de execução

O auditor fica na **Hospedagem**, junto do banco SQLite do Portal. Ele é `Type=oneshot` e não mantém processo residente. Esta é uma exceção deliberada à preferência pelo Faro para novos serviços auxiliares: mover a reconciliação para outro nó exigiria expor/copiar o SQLite ou criar acesso remoto ao banco local. A preferência pelo **Faro** continua válida para novos serviços autônomos que não dependem de acesso local ao estado do Portal.

Primeira prova manual em 22/11/2026:

- 25 IDs públicos indexados;
- 8 projetos operacionais avaliados;
- `issue_count=0` para as invariantes cobertas;
- `runtime_mutations_performed=false`;
- `secrets_included=false`.

## Fonte de verdade versus índice

O índice pode ser apagado e reconstruído. Ele não autoriza operação e não substitui:

- `cloudif-portal.db`;
- Executor/Komodo;
- Publisher/NPM;
- Forgejo;
- configuração de ambiente/secrets;
- runtime real dos containers.

Em conflito, a auditoria registra drift e o agente investiga a fonte canônica. Nunca corrigir runtime automaticamente apenas porque o cache divergiu.

## Continuidade para agentes

Antes de criar qualquer novo fluxo que aparece em Projetos/Publicações/Conectores/Aprovações:

1. identificar o estado canônico;
2. definir a chave/namespace do read-model;
3. definir evento de atualização em **todas** as mutações;
4. garantir stale-while-revalidate na leitura;
5. adicionar a reconciliação noturna se houver nova invariante relevante;
6. adicionar teste de regressão;
7. documentar rollback e preservar secrets.

Referências complementares:

- `docs/PADRAO-CLOUDIFF-PREVIEW-HOMOLOGACAO-PRODUCAO-20261120.md`;
- `docs/RUNBOOK-PADRAO-CLOUDIFF-WHP-CONTINUIDADE.md`;
- `docs/AUDITORIA-GLOBAL-PROJETOS-WHP-20261122.md`;
- `docs/REMEDIACAO-PORTAL-READMODEL-HISTORICO-20261122.md`.

## Inventário current x reserved-deleted — 23/11/2026

Referência canônica: `docs/AUDITORIA-GLOBAL-PROJETOS-CLOUDIFF-20261123.md`. `project_public_ids` preserva números de projetos excluídos e não é catálogo de projetos ativos. Read-model e recovery devem sempre cruzar com `projects`.
