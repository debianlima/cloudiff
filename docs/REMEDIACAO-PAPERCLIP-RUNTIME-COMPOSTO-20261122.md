# Paperclip P1025 — gate de runtime composto antes de Homologação

Data: 22/11/2026 UTC. Projeto: `paperclip`, public number 1025.

## Estado funcional confirmado

- W1 responde HTTP 200 e serve a interface `Paperclip`.
- `/api/health` responde `status=ok` e informa o commit `dfcaaf831438cf0402d54a5ede388c3dc66bf222`.
- Checkout local está limpo e alinhado: `HEAD == origin/main == dfcaaf831438cf0402d54a5ede388c3dc66bf222`.
- Produção D1 legada permanece intacta em `1025.cloudiff.duckdns.org` / `1025-d1.cloudiff.duckdns.org`.
- `assistente-interativo` não possui ACL do projeto; nenhuma H/P foi criada por impersonação.

## Arquitetura do Preview

O W1 é composto por dois containers:

- `cloudif-p1025-w1-preview-app`: aplicação real Paperclip, imagem versionada pelo commit, com volume persistente `cloudif-p1025-w1-paperclip-data`;
- `cloudif-p1025-w1-preview-web`: sidecar/gateway saudável que encaminha o tráfego público ao app.

O registro legado `project_preview_state.container` aponta para o gateway. O status ao vivo já é calculado corretamente pelo Komodo, porém o caminho genérico de `cloudif_preview_snapshot()` congelava o container registrado — portanto poderia congelar o gateway em vez da aplicação e também ignorar o volume persistente.

## Gate implantado

`cloudif_preview_snapshot()` agora identifica runtime composto antes de qualquer commit/snapshot quando:

1. existe um container irmão `cloudif-p<numero>-w<geracao>-preview-app`; ou
2. o container registrado possui `org.cloudiff.artifact-kind` indicando `sidecar`/`gateway`.

Nesses casos a operação retorna HTTP 409:

`preview_composite_runtime_requires_manifest`

com orientação para configurar manifest/runtime completo antes da Homologação.

O gate não afeta linked-compose nem multiservice, pois esses fluxos usam caminhos próprios de snapshot/deploy.

## Prova negativa

Foi chamada diretamente a operação de snapshot do Preview Paperclip com candidato sintético, sem passar pelo Portal:

- HTTP 409;
- `compositeAppDetected=true`;
- `candidate_count` continuou 0;
- nenhum artefato H foi criado;
- W1 `/api/health` continuou HTTP 200;
- D1/Produção continuou HTTP 200.

## Próximo passo correto

Paperclip ainda não possui manifest no Project Config Controller (`configuration_required`, ação `review_and_apply_manifest`). O runtime composto não deve ser inferido automaticamente porque o app mantém volume de dados e semântica própria.

Para migrar ao padrão W→H→P:

1. definir/revisar manifest completo do runtime Paperclip, incluindo app, gateway e política de dados/volume;
2. validar clone integral W→H sem compartilhar dados mutáveis indevidamente;
3. somente então habilitar Enviar para Homologação;
4. promover a própria H para P sem rebuild;
5. deixar D1 como histórico Offline após a nova P saudável.

Até esse contrato existir, bloquear H é mais seguro do que criar uma Homologação incompleta.
