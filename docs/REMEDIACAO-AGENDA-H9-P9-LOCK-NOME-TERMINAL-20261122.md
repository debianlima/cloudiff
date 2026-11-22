# Agenda P1020 — remediação H9→P9: nome, SQLite lock e Terminal de Produção

Data: 22/11/2026.

## Sintoma

Na promoção de H9 para Produção, a mecânica externa chegou a criar/ativar P9, mas o Portal exibiu falha na última operação com `database is locked`. A interface permaneceu com P8 ativa e H9 visível, criando a impressão de colisão de nome/numeração. O Terminal de Produção também passou a retornar erro.

## Diagnóstico

O job 94 já havia reservado corretamente `publication_number=9`; portanto o Portal não tentou numerar a candidata H9 como P8.

Antes da falha final:

- Executor já havia promovido `dep_6c524d61f1a4dbe384f47364` de H9 para `production`, preservando os mesmos containers;
- Publisher já possuía `1020-p9-publication`;
- alias `agendaunica` e projeto 1020 já apontavam para deploy 9;
- bridge P9 já carregava `cloudif-p1020-active-web`;
- Portal DB ainda mantinha P8 como ativa e H9 como `homologated`.

A falha ocorreu na fase de cleanup/progresso, quando `cloudif-portal-refresh-cache.service` iniciou uma rodada simultânea. O refresh mantinha uma conexão SQLite com transação de escrita enquanto realizava I/O de rede em `refresh_nodes()`. O callback de progresso da publicação disputou o mesmo banco e recebeu `database is locked`, abortando cleanup/finalização do Portal após o cutover já ter ocorrido.

O Terminal H/P Compose tinha outra divergência: o Portal/Komodo ainda consultava tabelas legadas `publication_runtimes` / `stage_production_releases`, que não representam deployments Compose gerenciados pelo Executor.

## Correções

### 1. Numeração e preflight de nome

A próxima P considera também números já reservados em jobs e requests, não apenas releases concluídas.

`_publication_for_candidate()` garante idempotência por candidata:

- retry da candidata 9 reutiliza P9;
- uma candidata nova recebe P10;
- se Pn já pertence a outra candidata, a promoção é bloqueada antes do cutover.

Antes da promoção Compose, `_compose_publication_preflight()` valida:

- Pn não ocupada por outra candidata no Portal;
- Pn não reservada por outro job;
- identidade/estado do deployment homologado no Executor;
- hostname Pn externo;
- caso o deployment já esteja em `production`, reconhece promoção parcial da **mesma** candidata em vez de criar novo número.

### 2. Recuperação idempotente

Se a promoção externa já aconteceu, o retry:

- não recria containers;
- não cria P seguinte;
- revalida/reaplica bridge, stage e alias Pn;
- conclui cleanup de H e Produção anterior;
- finaliza o Portal DB em transação curta `BEGIN IMMEDIATE`;
- marca candidata como `published` com a P originalmente reservada.

H9→P9 foi reconciliada com `recoveredPartialPromotion=true`, `sameInstanceAsHomologation=true` e `containersRecreated=false`.

### 3. Mutex lifecycle × read-model

Worker e refresh compartilham `/run/cloudif/portal-publication-lifecycle.lock`.

- o worker segura o lock durante todo job H/P;
- o refresh tenta lock não bloqueante;
- se publicação está ativa, retorna `DEFERRED` e espera a próxima rodada;
- após lifecycle, refresh volta a `OK` normalmente.

Além disso, `refresh_nodes()` não mantém mais transação SQLite aberta durante chamadas de rede: coleta dados primeiro e faz uma única escrita curta no final. Busy timeout dos caminhos críticos/read-model foi elevado para 30 s como defesa adicional.

### 4. Terminal Compose por deployment

Para `compose-snapshot`, o Terminal não usa tabelas legadas. O Portal envia o `deployment_id`; o Komodo valida diretamente:

- `cloudif-dep-<id>-web`;
- labels de deployment/projeto/serviço;
- container running/healthy.

Não exige `org.cloudiff.environment=production`, pois promoção same-instance preserva o container homologado e seus labels originais.

O Terminal de P9 foi validado com:

- container `cloudif-dep-6c524d61f1a4dbe384f47364-web`;
- `terminalReady=true`;
- `terminalSource=compose_deployment`;
- `sameRuntimeAcrossPromotion=true`.

## Estado após reconciliação

- P9: ativa e `published` no Portal;
- H9: candidata `published`, `published_publication_number=9`;
- job 94: `succeeded/completed`, marcado como reconciliado após lock técnico;
- Publisher P1020: somente W3 + P9;
- P8: inativa, runtime parado para histórico/rollback;
- H9 stage/bridge: removidos;
- alias `agendaunica` e `1020.cloudiff.duckdns.org`: P9;
- health P9/aliases: HTTP 200, revisão `18416127cdf9`.

Backup pré-reconciliação:
`/var/lib/cloudif/portal/backups/agenda-h9-p9-reconcile-20261122T163708Z`.

## Addendum de interface — identidade da Produção

O workspace de publicação não pode depender somente do estado transitório do job para atualizar ferramentas do ambiente. O módulo `publication-release.js` mantém a identidade da Produção ativa como `P<n>|deploymentId`.

Quando uma leitura nova de `release-flow` detecta mudança dessa identidade:

- dispara `cloudif:publication-state-changed` com `operation=production/identity-changed`;
- invalida o read-model visual do modal de ambientes;
- recarrega Terminal, PHP, Node.js, Site e Variáveis usando a nova Produção ativa;
- o asset recebe versão nova para impedir cache do JavaScript anterior.

Isso cobre inclusive reconciliações idempotentes em que o runtime já mudou e a interface ainda estava aberta mostrando a P anterior.
