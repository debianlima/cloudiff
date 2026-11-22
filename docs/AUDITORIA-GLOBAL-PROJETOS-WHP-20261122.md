# Auditoria global dos projetos — padrão CloudIFF Preview → Homologação → Produção

Data técnica: 2026-11-22 UTC (2026-11-21 America/Sao_Paulo).

## Escopo e método

Auditoria somente leitura dos 8 projetos cadastrados no Portal, cruzando:

- `projects`, `project_public_ids`, `publication_candidates`, `production_releases`, `project_publications`, `project_publication_aliases` e `project_preview_source_links`;
- `release_flow_status()` / estado do Preview;
- Komodo repo/stack status e hash conhecido;
- Executor Compose (`deployment_id`, snapshot e estado);
- Docker real na Forja/Hospedagem;
- HTTP/HTTPS das URLs W/H/P e aliases principais;
- contrato em `docs/RUNBOOK-PADRAO-CLOUDIFF-WHP-CONTINUIDADE.md`.

Nenhum runtime de projeto foi alterado nesta unidade.

## Resultado geral

| Projeto | Preview | Forgejo → Preview | Produção | H→P mesma instância | Histórico/resíduos | Classificação |
|---|---|---|---|---|---|---|
| `agenda-unica` | W3 saudável | alinhado | P7 + alias `agendaunica` saudáveis | **sim**, `dep_19bc...` em H7/P7 | P6/P3 Offline; P2 legado Offline | **CONFORME** |
| `cadales` | W1 contínuo saudável após migração v144 | alinhado `ad8e67c...` | P2 saudável | não comprovado; P2 é legado | W2/H2 removidos; D1/D2 metadata inativa | **PARCIAL — aguarda próximo H→P humano** |
| `cpuhub` | W2 saudável | alinhado (`97af1e3...`) | P5 saudável | não comprovado; fluxo antigo | H3 ainda `awaiting_homologation`; P2/P3 Offline | **PARCIAL / LEGADO** |
| `laboratorio-de-hardware` | W1 saudável após remediação | alinhado `3b399e9` | P12/alias saudáveis | **não** historicamente: H13 `dep_51a7...` → P12 `dep_210f...` | H11/H13/P5 agora Offline; snapshots preservados | **PARCIAL — aguarda novo H→P humano** |
| `msha` | não configurado | n/a | nenhuma | n/a | nenhum runtime de publicação | **DRAFT / N/A** |
| `paperclip` | W1 saudável após correção de healthcheck | hash `dfcaaf8...` alinhado | D1 legado permanece placeholder | n/a | resíduos W1 removidos; volume preservado | **PARCIAL — aguarda H→P humano** |
| `sgrep-v2` | W1 source-linked saudável e reconhecido | source commit `f29f752...` | nenhuma | n/a | resíduos exited removidos; Terminal source-linked pendente | **PARCIAL — read-model conforme** |
| `silvipro` | W1 contínuo saudável | alinhado `ad2273de...` | P1 real reconciliada + alias `silvipro` | não comprovado; P1 importada como legado | D1 histórico; D2 parado; W2 removido | **PARCIAL — aguarda novo H→P humano** |

## 1. Agenda Única — conforme

- Public number 1020.
- Preview fixo W3: `1020-w3-preview.cloudiff.duckdns.org`, HTTP 200.
- Preview Git: `1841612...`, status `synced`.
- Produção ativa P7 e alias `agendaunica.cloudiff.duckdns.org`: HTTP 200, mesma revisão observada.
- H7 e P7 usam o mesmo `deployment_id` `dep_19bc037d073bf2418f9050c7` e o mesmo snapshot `snap_29103714e0b1ac96c11b8955`.
- P6 e P3 terminam Offline; P6 possui reidratação histórica comprovada; P2 é legado Offline.

Nota importante: labels Docker dos containers promovidos podem ainda indicar `homologation` porque labels são imutáveis. **Não recriar containers só para alterar label**; a identidade preservada é justamente a prova do H→P in-place.

## 2. Cadales — W1 contínuo sincronizado; P2 ainda legado

- Public number 1022; W1, P2 e alias `cadales` respondem HTTP 200.
- O mecanismo v144 migrou o W2 legado para o Preview contínuo W1 `cloudif-p1022-preview-web` com alias Docker `cloudif-p1022-w1-preview-web`.
- Checkout e `origin/main` estão em `ad8e67cee97f12f0c3826d46ded8f612add2ba2f`, dirty=false.
- O W2 e o stage H2 foram removidos do Publisher; o container H2 foi removido após backup e prova de mesma imagem que P2, sem volume de dados.
- Metadata Komodo legada D1/D2 ficou `inactive`; a P2 moderna é a única Produção `is_active=1`.
- H2/P2 continuam sem metadados `sameInstancePromotionRequired`/`homologationDeploymentId`; portanto P2 é legado e não prova promoção da mesma instância.
- `assistente-interativo` não possui ACL do projeto; o próximo H→P precisa ser iniciado pelo proprietário.

### Próximo passo

Usar o W1 atual como origem da próxima Homologação e promover a mesma instância para a próxima P. Somente depois P2 deve virar histórico/offline. Evidência: `docs/REMEDIACAO-CADALES-W1-SYNC-20261122.md`.

## 3. CPUHub — operacional, mas ainda legado no ciclo de release

- Public number 1021; W2 e P5 respondem HTTP 200.
- Bind W2 está em `97af1e386fabb9b718f8aa100f200acfe6333264`, igual ao `latest_hash` conhecido.
- Komodo Stack ainda falha pela expectativa de `docker-compose.yml`, apesar do Preview real saudável.
- H5/P5 não possuem metadados do contrato atual de mesma instância.
- H3 permanece `awaiting_homologation` mesmo após H4/P3 e H5/P5, configurando resíduo de estado.
- P2/P3 estão Offline, como desejado para histórico.

### Remediação segura

Reconciliar o Stack gerenciado, superseder H3 residual por regra de estado e usar o fluxo atual no próximo H→P. Não há motivo para interromper P5 antes disso.

## 4. Laboratório de Hardware — maior prioridade

- Public number 1001.
- W1 retorna HTTP 502; bridge `cloudif-p1001-w1-preview-web` está exited.
- P12/alias `labhard` respondem e redirecionam para o login da aplicação.
- H13 usa `dep_51a7b4cfef7adfc42e38700d`, snapshot `snap_3d74a8268ba7ca3881a9075a`.
- P12 usa **outro deployment**, `dep_210f7ec700eca6fb3353914b`, embora use o mesmo snapshot. Isso é o modelo antigo de reconstrução e viola “mesma instância H→P”.
- H13 continua com runtime/bridge ativos; H11/H12 e outros estados antigos também deixaram resíduos.
- P5 histórica tem `dep_74a4...` em estado `failed`: app exited, DB ainda running; URL P5 retorna 502.
- Existem H2/H3/H5/H6 ainda marcadas `awaiting_homologation`/`homologated` apesar de releases posteriores.

### Ordem obrigatória de remediação

1. restaurar W1 fixo e validar health externo;
2. reconciliar estados H antigos como superseded sem apagar evidência;
3. parar/remover runtimes H residuais somente após mapear snapshot/rollback;
4. criar **nova** Homologação a partir do W1 restaurado;
5. validar H e promover a própria instância para a próxima P;
6. só após a nova P saudável desativar P12;
7. tratar P5 como histórico quebrado e preservar snapshot antes de qualquer limpeza.

Não tentar “converter” P12 atual em mesma-instância por alteração de metadados: a diferença de deployment é factual.

## 5. MSHA — draft sem runtime

- Projeto `draft`, sem public number efetivo de publicação, sem Preview e sem Produção.
- Komodo conhece repo/stack, mas deploy não está pronto.

Sem não conformidade operacional enquanto permanecer intencionalmente `draft`. Se o usuário pedir Preview, o provisionamento deve entrar diretamente no padrão atual.

## 6. Paperclip — Preview real falha e Produção é placeholder legado

- Public number 1025.
- W1 retorna HTTP 200, mas o conteúdo da própria aplicação informa `Paperclip couldn’t start`; por isso `release_flow_status` corretamente marca `healthy=false`.
- Source commit do Preview `dfcaaf831438cf0402d54a5ede388c3dc66bf222` coincide com o `latest_hash` do Komodo.
- Produção ativa é D1 legado. `1025.cloudiff.duckdns.org` exibe `paperclip · primeiros passos` / `Seu projeto está publicado.`, não a interface Paperclip.
- Há runtime W1 restaurado (`cloudif-p1025-w1-preview-app`) e gateway W1, além de resíduos de rollback/canary exited.
- Não há H/P moderno.

### Remediação segura

Corrigir a inicialização funcional no W1 primeiro. Não promover enquanto o W1 só responde HTTP 200 com erro de aplicação. Depois gerar a primeira H moderna e substituir D1 somente após homologação.

## 7. SGREP v2 — Preview source-linked reconhecido

- Projeto continua `draft`, public number 1026.
- `project_preview_source_links` registra W1 online, source commit `f29f752f2aadbdad46b46570b29b2895007fb6cb`, fonte readonly e dados isolados.
- O Portal agora reconhece esse contrato como `runtimeKind=source-linked-preview`, valida a URL externamente e mostra W1 saudável.
- Diagnóstico Node aponta para `cloudif-sgrep-v2-preview-app` (Node 24.22.3); PHP é corretamente reportado como ausente.
- `public_external_verified=1` após prova HTTP.
- Cinco containers exited de smoke/rollback foram removidos após backup; app/db/sat/gateway ativos foram preservados.
- O Stack Komodo legado ainda reporta `deploy_status=failed`; isso não representa o W1 source-linked e não deve ser usado como health do Preview.
- Terminal source-linked continua pendente de contrato explícito para selecionar `preview-app` com ACL/labels; não redirecionar para outra Stack.

Evidência: `docs/REMEDIACAO-SGREP-V2-PREVIEW-READMODEL-20261122.md`.

## 8. SilviPro — W1 contínuo recuperado, P1 real reconciliada

- Public number 1002.
- W1 contínuo agora responde HTTP 200 e usa o checkout Git `ad2273de...`; chamadas `ensure` repetidas preservam W1, stack e container.
- O bug v143 que incrementava Wn na recuperação foi corrigido materializando o v144 live; o container contínuo mantém alias Docker público `cloudif-p1002-w1-preview-web`.
- P1 (`cloudif-p1002-p1-publication-web`) é a Produção real: possui `cloudif-p1002-active-web` e serve exatamente o mesmo conteúdo de `1002.cloudiff.duckdns.org` e `silvipro.cloudiff.duckdns.org`.
- O Portal foi reconciliado: D1 ficou histórico/inativo e P1 foi importada como legado ativo, sem inventar Homologação nem marcar same-instance.
- D2, sem alias ativo nem rota, foi parado; W2 residual foi removido do Publisher.
- `assistente-interativo` não possui ACL do projeto; a próxima H/P pelo contrato atual deve ser iniciada pelo proprietário.

### Próximo passo

O proprietário deve enviar o W1 atual para Homologação e promover essa mesma instância para a próxima P. Só após a nova P saudável, P1 passa a histórico/offline. Evidência detalhada: `docs/REMEDIACAO-SILVIPRO-P1002-20261122.md`.

## Resíduos de host relevantes

### Forja

- Agenda: P3/P6 históricos exited/preservados; aceitáveis enquanto `canDelete=true`. P7 ativo conforme.
- CPUHub/Cadales: vários `dN` antigos exited; são legado e podem ser inventariados para limpeza posterior, sem urgência funcional.
- Laboratório: múltiplos deployments H parcialmente/running — **resíduo ativo prioritário**.
- Paperclip: canary/rollback antigos exited; Preview atual running.
- SGREP: smoke/image-test/rollback exited; Preview atual running.
- SilviPro: D2/P1 ativos sem correspondência limpa no modelo do Portal.

### Hospedagem

Restam containers Agenda antigos exited (`cloudif-agenda-unica-api-1/web-1`) sem função no runtime atual. São candidatos a limpeza futura após confirmar que nenhuma unit/systemd os referencia.

## Prioridade de remediação

1. **P1 — Laboratório de Hardware:** W1 502 + H→P diferente + H residual.
2. **P1 — SilviPro:** produção placeholder + rotas D1/D2/P1 incoerentes.
3. **P1 — Paperclip:** Preview funcionalmente falho + produção placeholder.
4. **P1 — Cadales:** Preview fixo atrasado em relação ao Forgejo e falso `synced`.
5. **P2 — SGREP v2:** Preview real não reconhecido pelo read-model.
6. **P2 — CPUHub:** migrar sem downtime do ciclo legado para H→P same-instance e limpar H3.
7. **N/A — MSHA:** nenhuma ação enquanto draft.
8. **Conforme — Agenda Única:** usar como referência de aceite/regressão.

## Portões para qualquer correção futura

Para cada projeto, abrir unidade separada com lease própria e preservar Produção ativa até existir rollback comprovado. O agente deve:

1. reler `docs/RUNBOOK-PADRAO-CLOUDIFF-WHP-CONTINUIDADE.md`;
2. capturar prestate de W/H/P/alias/containers;
3. corrigir somente uma classe de drift por vez;
4. validar Preview e, quando aplicável, nova H;
5. promover somente a mesma instância homologada;
6. provar health do alias antes de desativar a P anterior;
7. deixar P históricas Offline;
8. registrar evidência, backup e rollback;
9. nunca usar HTTP 200 isolado como prova de aplicação saudável (Paperclip demonstra o motivo).
