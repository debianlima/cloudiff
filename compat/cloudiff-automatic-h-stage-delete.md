# CloudIFF — cleanup automático da Homologação após promoção H → P

## Contrato

Após a própria instância homologada ser promovida para Produção, o pipeline deve concluir automaticamente o cutover nesta ordem:

1. criar/validar a rota P;
2. ativar P e o domínio estável;
3. validar health/readback do domínio estável;
4. `POST /stage/delete` para a H promovida;
5. desativar o bridge H;
6. desativar a Produção anterior, preservando rollback;
7. persistir P como ativa e H como histórico promovido.

O passo 4 remove somente o estágio/vhost do Publisher e preserva o certificado. O deployment H não é destruído: ele já é a própria Produção.

## Runtime Portal

O runtime ativo recebeu `_publisher_delete_stage(...)` e chama `/stage/delete` somente **depois** do health/readback da Produção nova e **antes** de desligar o bridge de Homologação. O resultado é persistido em `homologationStageRemoved` e `homologationCertificatePreserved`.

O patch `cloudiff-automatic-h-stage-delete-portal.patch` é incremental sobre o backup imediatamente anterior à mudança e deve permanecer como fonte de reconciliação enquanto a árvore canônica do Portal não estiver totalmente alinhada ao release ativo.

## Publisher v17 live

A fonte C++ atual já implementa `POST /stage/delete` de forma idempotente e possui teste unitário para remoção + repetição sem efeito. O contrato `contratos/npm-publisher.schema.json` passa a anunciar a nona rota.

A release live deve ser construída por `deploy/build_npm_publisher_release.sh` e promovida por `deploy/install_npm_publisher_live_release.sh`, que exigem:

- `source_commit` e `source_tree` exatos;
- SHA-256 e GNU BuildID do binário;
- clang e digest do comando de build;
- teste `npm_publisher_provider` PASS;
- canary do `/stage/delete` sobre chave inexistente, com zero drift semântico do state e zero drift do Nginx;
- backup de `state.json` e `http.conf`;
- rollback automático por symlink + restauração dos backups se smoke/health/nginx falhar.

Tokens de Publisher não são gravados nem passados por argv. Os probes usam processo Python com o token apenas em memória do processo e nunca persistem o valor em arquivo/log.

## Release efetiva — 21/11/2026

- live: `/opt/cloudiff-v2/releases/20261121T102627Z-v17-npm-publisher-stage-delete-ea4c01c`;
- previous: v14 `20261111T1725Z-v14-npm-publisher-maint-2c6b10a`;
- `source_commit`: `ea4c01c030d281f5e1869a618fe1737b2f5ab18c`;
- `source_tree`: `2668ce4065d0fc5b6cded733989e3d8ef23cccd0`;
- binário SHA-256: `4285033213b925750938d9ceb5e5316e6547dcda61257fd573777a5bfab4cf31`;
- GNU BuildID: `1727c5cf73d913a5d70f38a788d03591fd760f75`;
- installer commit: `6f994ba6093b3dd3f9fd4aa7053a052eb7dd34af`;
- installer SHA-256: `d09c21f50a099018027d2ccda0a8bb96a793ae9f920f8db52f689cd5e50c393c`;
- clang: 21.1.8; `npm_publisher_provider` 1/1 PASS;
- canary `/stage/delete` idempotente: HTTP 200, `removed=false`, state semântico e `http.conf` byte-idênticos;
- `nginx -t`: PASS;
- ingress real `cloudif-publisher.internal/stage/delete`: HTTP 200;
- smoke local do vhost e smoke externo por LabIFF: PASS;
- P3/`1020`/`agendaunica`: HTTP 200, revisão `e32213d0b4d2`.

Candidates anteriores foram mantidos como evidência e rotulados: v15 `REJECTED_CANARY`; v16 `REJECTED_SMOKE`. Nenhum deles ficou live.
