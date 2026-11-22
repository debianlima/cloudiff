# Remediação — Cadales P1022 — Preview contínuo e limpeza de resíduos

Data: 22/11/2026 UTC. Projeto: `cadales`, public number 1022.

## Estado inicial

- Preview legado estava em W2, container `cloudif-p1022-w2-preview-web`, commit `0599c7985678491878fe987da2ead65d957d1371`.
- Komodo/Forgejo já anunciava `ad8e67cee97f12f0c3826d46ded8f612add2ba2f` como versão atual.
- O Portal marcava o Preview como `synced`, gerando falso positivo.
- P2 estava ativa e saudável e não podia ser tocada.
- H2 (`cloudif-p1022-d2-web`) permanecia running mesmo depois de P2 ter sido publicada.
- Publisher ainda mantinha stages W2 e H2.

## Migração para Preview contínuo v144

O endpoint oficial `preview/ensure` do Komodo v144 reconciliou o Preview para o runtime contínuo da plataforma:

- stack: `cloudif-p1022-preview`;
- container: `cloudif-p1022-preview-web`;
- alias Docker público: `cloudif-p1022-w1-preview-web`;
- stage público: W1;
- checkout Git: `ad8e67cee97f12f0c3826d46ded8f612add2ba2f`;
- `origin/main` igual ao checkout, dirty=false;
- container `running/healthy`.

O W2 legado foi removido pelo mecanismo de migração. W1 passou a responder HTTP 200 e o read-model do Portal passou a retornar `configured=true`, `healthy=true`, `stageCode=W1`, Git `synced` em `ad8e67c...`.

A camada v144 atual define Preview contínuo W1 para projetos genéricos. O caso Agenda W3 é uma exceção linked-compose/histórica e não deve ser generalizado para estes runtimes.

## Limpeza de resíduos

Foram removidos do Publisher:

- stage W2 obsoleto;
- stage H2 já publicado.

O container H2 `cloudif-p1022-d2-web` foi removido após:

- backup de `docker inspect` em `/srv/cloudif/backups/cadales-h2-residual-20261122T024459Z`;
- prova de que H2 e P2 usam exatamente a mesma imagem `sha256:663ad6215c80e9ff859419b33b09fd4444947e385ddd2c00b15bb1306e4bcc99`;
- prova de que H2 não possuía volume de dados, apenas bind readonly de `runtime.env`.

A P2 `cloudif-p1022-p2-publication-web` permaneceu `running/healthy` e manteve o alias ativo.

## Reconciliação de metadata legada

`publication_runtimes` ainda marcava D1 como `is_active=1`, embora D1 estivesse exited e a Produção real fosse P2 na tabela `stage_production_releases`.

Foi preservado backup do banco Komodo Agent em:

`/srv/cloudif/backups/cadales-komodo-readmodel-20261122T024756Z`

Estado final:

- D1: `inactive`, `is_active=0`;
- D2/H2: `inactive`, `is_active=0`;
- P2 moderna: `ready`, `is_active=1`.

## Estado final

- W1: HTTP 200, commit `ad8e67c...`, saudável e sincronizado;
- W2: sem stage/runtime ativo; hostname cai no fallback da plataforma;
- H2: sem stage/runtime ativo;
- P2: HTTP 200 e saudável;
- `cadales.cloudiff.duckdns.org`: HTTP 200;
- única Produção ativa: P2.

## Lacuna restante

H2/P2 pertencem ao fluxo legado e não possuem `homologationDeploymentId`, `productionDeploymentId` ou prova de `sameInstancePromotionRequired`. Não alterar metadata para fingir conformidade.

A identidade `assistente-interativo` não possui ACL do projeto no Portal. Assim, a migração definitiva deve ocorrer na próxima publicação iniciada pelo proprietário:

1. validar W1 atual;
2. enviar W1 para nova H;
3. homologar;
4. promover a mesma instância H→P;
5. deixar P2 histórica/offline apenas depois do novo cutover saudável.
