# Remediação — Paperclip P1025 — saúde do Preview W1

Data: 22/11/2026 UTC. Projeto: `paperclip`, public number 1025.

## Diagnóstico inicial

O Portal marcava W1 como `healthy=false` e a leitura simples do HTML mostrava `Paperclip couldn’t start`.

A análise do runtime mostrou que esse diagnóstico era incompleto:

- `cloudif-p1025-w1-preview-app` estava `running` e executando scheduler/backups normalmente;
- `/api/health` pelo hostname público respondia HTTP 200 com `status=ok`, `bootstrapStatus=ready`, backup de banco `status=ok` e commit `dfcaaf831438cf0402d54a5ede388c3dc66bf222`;
- `/api/auth/get-session` retornava 401 sem sessão, comportamento esperado;
- o HTML inicial contém a mensagem de fallback antes da inicialização JavaScript e não deve ser usado sozinho como prova de falha.

O falso negativo vinha do gateway `cloudif-p1025-w1-preview-web`: ele estava `running`, porém sem Docker healthcheck. `_cloudif_wait_health()` exige `running|healthy`, logo o read-model devolvia `healthy=false`.

## Correção do gateway

Foi criado um sidecar Nginx canário idêntico ao gateway existente, com:

- mesma imagem;
- mesma rede `cloudif-publications`;
- mesma configuração `sidecar.conf` readonly;
- mesmos labels de artefato/commit;
- healthcheck real em `http://127.0.0.1/api/health`, exigindo `status=ok`.

O canário chegou a `healthy`, foi validado internamente e então substituiu o gateway canônico. O gateway antigo foi removido após validação externa. Backup do `docker inspect` foi salvo em `/srv/cloudif/backups/paperclip-w1-gateway-health-20261122T023653Z`.

Resultado:

- `cloudif-p1025-w1-preview-web`: `running/healthy`;
- `release_flow_status()` passou a informar W1 `configured=true`, `healthy=true`;
- `1025-w1-preview.cloudiff.duckdns.org/api/health`: HTTP 200;
- volume `cloudif-p1025-w1-paperclip-data` preservado;
- `preview-app` não foi recriado nem interrompido.

## Limpeza de resíduos

Após backup de `inspect`, foram removidos somente containers `exited`:

- `cloudif-p1025-w1-dbrestore-canary`;
- `cloudif-p1025-w1-preview-app-empty-rollback-20261119`;
- `cloudif-p1025-w1-preview-web-apache-backup`;
- `cloudif-p1025-w1-preview-web-old`.

O canário DB referenciava o volume vivo, mas `docker rm` removeu apenas o container. O volume permanece presente e em uso pelo Preview atual.

Backup: `/srv/cloudif/backups/paperclip-w1-residual-containers-20261122T023738Z`.

## Produção

A Produção continua sendo D1 legada/placeholder em `1025.cloudiff.duckdns.org`. Nenhum cutover foi executado.

A identidade real `assistente-interativo` não possui ACL no projeto, portanto não foi criada H nem P por impersonação.

## Próximo passo humano

O proprietário pode agora usar o W1 saudável como origem do fluxo padrão:

1. conferir o Paperclip autenticado no W1;
2. enviar W1 para Homologação;
3. homologar;
4. promover a mesma instância H→P pelo Portal;
5. somente depois desligar/substituir o D1 legado.

## Regra global aprendida

Não classificar uma SPA como quebrada apenas pelo HTML inicial/fallback. Para runtimes autenticados, o health deve usar endpoint funcional do backend e estado do gateway/container.
