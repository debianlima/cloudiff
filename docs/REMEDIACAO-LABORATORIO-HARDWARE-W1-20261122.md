# Remediação — Laboratório de Hardware P1001 — W1 e resíduos históricos

Data: 22/11/2026 UTC. Projeto: `laboratorio-de-hardware`, public number 1001.

## Escopo

Remediação reversível do Preview e de runtimes históricos, sem alterar a Produção ativa P12.

## Estado inicial

- W1: HTTP 502; bridge `cloudif-p1001-w1-preview-web` exited.
- Stack Komodo no commit `3b399e9f72133b63a9471ccc25e7af50fedeba30`, mas `lab_hardware_db` e `lab_hardware_app` estavam parados.
- H11 e H13 tinham deployments Compose ainda `running` apesar de já publicados.
- P5 histórica estava `failed` com DB ainda running.
- P12 e alias `labhard.cloudiff.duckdns.org` estavam saudáveis e não podiam sofrer alteração durante esta unidade.

## Correção do W1

1. Stack existente foi iniciado pelo endpoint oficial Komodo `stack/start`; não houve rebuild nem troca de checkout.
2. MySQL ficou `healthy` e `lab_hardware_app` voltou a `running`.
3. Bridge W1 foi garantida pelo helper oficial `_compose_source_preview_bridge()`.
4. Stage Preview W1 foi garantido no Publisher.
5. W1 passou a responder 302 para `/login.php`, comportamento normal da aplicação.
6. Komodo confirmou `latest_hash == deployed_hash == 3b399e9` e runtime `running`.
7. `release_flow_status()` passou a informar `configured=true`, `healthy=true`, `stageCode=W1`.

## Limpeza reversível de resíduos

H11 (`dep_85753ce731a96277937d5c5f`) e H13 (`dep_51a7b4cfef7adfc42e38700d`):

- rota H removida do Publisher;
- bridge H removida;
- deployment desativado;
- containers app/db parados;
- `resourcesPreserved=true` e `volumesRemoved=0`.

P5 (`dep_74a4eee5db0811874afd2448`):

- rota/bridge P5 removidas;
- deployment `failed` desativado;
- DB residual parado;
- snapshot e volumes preservados;
- a URL P5 agora cai no fallback padrão do Portal; não existe entrada P5 no Publisher nem bloco Nginx P5.

P12 (`dep_210f7ec700eca6fb3353914b`) permaneceu running/healthy durante toda a operação.

## Portões finais

- `1001-w1-preview`: saudável.
- `1001-p12-publication`: saudável.
- `labhard.cloudiff.duckdns.org`: saudável.
- H11/H13: inactive, sem bridge ativo.
- P5: inactive, sem bridge/stage ativo.
- P12: única Produção ativa.
- Forgejo/Komodo Preview: `latest_hash == deployed_hash == 3b399e9`.

## Lacuna restante

A P12 atual continua sendo legado anterior ao contrato same-instance: H13 usou `dep_51a7...`, P12 usa `dep_210f...`. Isso é fato histórico e não deve ser “corrigido” por alteração de metadata.

A identidade real `assistente-interativo` não possui acesso ao projeto no Portal (`PermissionError: Projeto não encontrado ou sem permissão.`). Portanto **não** foi criada H nova nem P nova por impersonação.

Para concluir a migração ao padrão atual, o proprietário deve, pela interface humana:

1. enviar o W1 atual para Homologação;
2. validar a nova H;
3. usar `Enviar para Produção`;
4. confirmar que H e P usam o mesmo `deployment_id` e que H residual é removido automaticamente;
5. somente depois considerar a P12 histórica/offline.

O backend atual já implementa `sameInstancePromotionRequired=true` para linked-compose e bloqueia reconstrução entre H e P.
