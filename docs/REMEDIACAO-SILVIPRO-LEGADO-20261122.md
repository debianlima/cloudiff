# SilviPro P1002 — reconciliação de Preview/Produção legada

Data: 22/11/2026 UTC. Projeto: `silvipro`, public number 1002.

## Conclusão

O conteúdo `silvipro · primeiros passos` não é erro do CloudIFF: ele está versionado no próprio Forgejo, commit `ad2273de08fac6189d19b2f8009b56157b0be594`, em `index.html`. Portanto não existe uma aplicação SilviPro mais nova a recuperar.

## Preview

- `project_preview_state`: W1 online, commit `ad2273de...`, container `cloudif-p1002-preview-web`.
- Container W1 saudável, imagem `cloudif/publication-p1002-d2:php8.3-node22`, image id `sha256:da3372e...`.
- O container possui alias de rede `cloudif-p1002-w1-preview-web`.
- `release_flow_status/preview_status` reconhece W1 como `configured=true`, `healthy=true`.
- `1002-w1-preview.cloudiff.duckdns.org` responde 200 e serve exatamente o conteúdo atual do Git.

## Produção real

- `stage_production_releases` registra P1 ativa, container `cloudif-p1002-p1-publication-web`, mesma imagem `sha256:da3372e...`.
- P1 possui alias de rede `cloudif-p1002-active-web`.
- O Publication Gateway resolve:
  - W1 → `cloudif-p1002-w1-preview-web`;
  - P1 → `cloudif-p1002-p1-publication-web`;
  - `1002.cloudiff` → `cloudif-p1002-active-web`.
- O alias `silvipro.cloudiff.duckdns.org` reescreve o Host para `1002.cloudiff.duckdns.org` antes de entrar no gateway.
- Portanto Preview e Produção são containers distintos apesar de compartilharem a mesma imagem/conteúdo.

## D2

`cloudif-p1002-d2-web` está exited e não participa do Publisher/Nginx ativo. Não foi necessário removê-lo nesta unidade.

## Drift legado restante

O Portal DB antigo ainda registra D1 em `project_publications` como Produção ativa, enquanto o runtime moderno de estágio registra P1. Não é seguro inventar retroativamente uma H/P moderna ou alterar metadata para afirmar uma promoção que não ocorreu.

O projeto deve permanecer classificado como **legado operacionalmente coerente** até o próximo ciclo real:

1. usuário altera o Forgejo;
2. W1 sincroniza a mesma URL;
3. usuário envia W1 para H pelo Portal;
4. H é validada;
5. a própria H é promovida para nova P;
6. só então P1/D1 legado vira histórico.

A identidade `assistente-interativo` não possui ACL do projeto; não houve impersonação nem nova publicação.
