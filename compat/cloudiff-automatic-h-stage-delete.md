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

## Publisher v15

A fonte C++ atual já implementa `POST /stage/delete` de forma idempotente e possui teste unitário para remoção + repetição sem efeito. O contrato `contratos/npm-publisher.schema.json` passa a anunciar a nona rota.

A release live deve ser construída por `deploy/build_npm_publisher_release.sh` e promovida por `deploy/install_npm_publisher_live_release.sh`, que exigem:

- `source_commit` e `source_tree` exatos;
- SHA-256 e GNU BuildID do binário;
- clang e digest do comando de build;
- teste `npm_publisher_provider` PASS;
- canary do `/stage/delete` sobre chave inexistente, com zero drift semântico do state e zero drift do Nginx;
- backup de `state.json` e `http.conf`;
- rollback automático por symlink + restauração dos backups se smoke/health/nginx falhar.

Tokens de Publisher não são gravados nem passados por argv; o instalador injeta o header `X-CloudIF-Token` via stdin do `curl`.
