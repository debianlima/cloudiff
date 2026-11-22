# Remediação — SilviPro P1002 — Preview fixo W1 e read-model de Produção

Data: 22/11/2026 UTC. Projeto `silvipro`, public number 1002.

## Estado encontrado

- Portal registrava apenas D1 como Produção ativa.
- Runtime real já possuía P1 (`cloudif-p1002-p1-publication-web`) com alias Docker `cloudif-p1002-active-web`.
- D2 (`cloudif-p1002-d2-web`) era runtime de materialização sem alias ativo.
- Publisher não tinha stage P1; W1/D2/P1 versionados caíam no fallback do Portal.
- Não existia `project_preview_state` no Komodo Agent.
- Git do projeto estava limpo e alinhado em `ad2273de08fac6189d19b2f8009b56157b0be594` (`Teste`).

## Preview

A primeira materialização pelo mecanismo v143 criou W1, mas uma recuperação subsequente incrementou para W2 porque `_cloudif_preview_create()` fazia `generation = old + 1` quando o container registrado desaparecia.

A árvore canônica já continha o v144 de Preview contínuo, mas o live ainda não o tinha. O v144 foi materializado incrementalmente no Komodo Agent, preservando hotfixes live existentes.

Correção adicional canônica: o container contínuo `cloudif-p1002-preview-web` mantém o alias de compatibilidade pública `cloudif-p1002-w1-preview-web`, exigido pelo gateway `10.62.91.2:18150`.

Após migração:

- `generation=1`, `stageCode=W1`;
- stack persistente `cloudif-p1002-preview`, id `6b0254d5219c5cb11c682765`;
- container contínuo `cloudif-p1002-preview-web`;
- aliases Docker incluem `cloudif-p1002-w1-preview-web`;
- Git `head == origin == ad2273de...`, dirty=false;
- duas chamadas `ensure` seguidas retornaram W1 e o mesmo stack/container;
- chamada adicional preservou o mesmo container ID `a0b595eb...`;
- W1 externo e `/api/health` respondem HTTP 200;
- W2 residual foi removido do Publisher e não há container W2.

Patch reproduzível do delta live: `compat/cloudiff-komodo-v144-fixed-preview-live.patch`.

## Produção real e reconciliação do Portal

A origem P1/D2 foi comprovada por conteúdo:

- `index.html`, `api/package.json` e `api/server.js` de D2 são byte a byte iguais ao commit `ad2273de...`;
- P1, D2, W1, `1002.cloudiff.duckdns.org` e `silvipro.cloudiff.duckdns.org` apresentaram o mesmo SHA256 de corpo `4a80098a...`;
- P1 é o único container de Produção com alias `cloudif-p1002-active-web`.

O Portal foi reconciliado com backup SQLite em `/var/lib/cloudif/portal/backups/silvipro-readmodel-20261122T023829Z/cloudif-portal.db`:

- D1 foi marcado inativo, preservado como histórico;
- P1 foi importada como Produção ativa, `deploy_number=2`, `candidate_number=1`;
- detalhe registra `legacyImported=true`, `sameInstancePromotionRequired=false` e não inventa Homologação;
- P1 versionada foi registrada no Publisher e passou a responder HTTP 200;
- D2, sem alias ativo nem rota pública, foi somente parado; seu inspect foi preservado em backup na Forja.

O read-model final mostra P1 como `activeModern`, W1 saudável e `primaryHostname=silvipro.cloudiff.duckdns.org`.

## Lacuna restante

P1 é legado importado e não prova H→P same-instance. `assistente-interativo` não possui ACL do projeto no Portal, portanto não foi criada nova Homologação nem nova Produção por impersonação.

O proprietário deve usar o W1 atual para criar a próxima H e promover a mesma instância para a próxima P. Só depois P1 deve se tornar histórica/offline pelo fluxo normal.
