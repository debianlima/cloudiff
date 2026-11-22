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
| `cpuhub` | W1 contínuo saudável | alinhado `97af1e3...` | P5 saudável | não comprovado; P5 é legado | H3 superseded; H2–H5/W2 sem rota; D2–D5 removidos; P2/P3 Offline | **PARCIAL — aguarda próximo H→P humano** |
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

## 3. CPUHub — W1 contínuo e legado limpo; P5 preservada

- Public number 1021; W1, P5, `1021.cloudiff` e alias `cpuhub` respondem HTTP 200.
- Preview contínuo W1 está em `97af1e386fabb9b718f8aa100f200acfe6333264`, status `synced`.
- P5 é a única Produção ativa no read-model moderno.
- H3 antiga foi marcada `superseded`; H2/H4/H5 permanecem apenas como histórico `published`.
- Stages W2, H2–H5 e P2/P3 foram removidos do Publisher. URLs antigas caem no fallback do Portal, sem upstream 502.
- Containers H legados D2–D5 foram removidos após backup; imagens/stacks preservados e sem volumes de dados.
- D5 era duplicata exata da imagem de P5 e não possuía alias ativo. P5 permaneceu running/healthy com `cloudif-p1021-active-web`.
- P2/P3 permanecem Offline e podem ser reativadas pelo Histórico.
- P5 não comprova H→P same-instance e continua classificada como legado.
- `assistente-interativo` não possui ACL do projeto; próximo H→P deve ser iniciado pelo proprietário.

Evidência: `docs/REMEDIACAO-CPUHUB-LEGADO-20261122.md`.
## 4. Laboratório de Hardware — W1 recuperado; P12 legado preservado

- Public number 1001.
- W1 foi recuperado sem rebuild: Stack existente voltou via Komodo, MySQL ficou healthy, app running e bridge W1 foi republicada.
- Forgejo/Komodo do Preview estão alinhados em `3b399e9f72133b63a9471ccc25e7af50fedeba30`.
- P12 e alias `labhard` permaneceram saudáveis durante toda a remediação.
- H11 e H13 foram desativadas com snapshots/volumes preservados; bridges e rotas H removidas.
- P5 histórica parcialmente viva foi desativada; DB residual parou; snapshot permaneceu preservado.
- A P12 atual continua legado factual: H13 usava `dep_51a7...`, P12 usa `dep_210f...`. Não alterar metadata para mascarar essa diferença.
- `assistente-interativo` não possui ACL do projeto; a primeira migração ao contrato atual precisa ser iniciada pelo proprietário.

### Próximo passo

Usar o W1 saudável como origem de uma nova Homologação e promover **a própria instância H** para a próxima P. Somente depois P12 deve virar histórico/offline. Evidência: `docs/REMEDIACAO-LABORATORIO-HARDWARE-W1-20261122.md`.
## 5. MSHA — draft sem runtime

- Projeto `draft`, sem public number efetivo de publicação, sem Preview e sem Produção.
- Komodo conhece repo/stack, mas deploy não está pronto.

Sem não conformidade operacional enquanto permanecer intencionalmente `draft`. Se o usuário pedir Preview, o provisionamento deve entrar diretamente no padrão atual.

## 6. Paperclip — W1 saudável; runtime composto protegido contra snapshot genérico

- Public number 1025.
- W1 responde HTTP 200 e `/api/health` confirma `status=ok` no commit `dfcaaf831438cf0402d54a5ede388c3dc66bf222`.
- O HTML inicial que dizia `Paperclip couldn’t start` era fallback transitório; o backend atual está saudável.
- Preview é composto: `cloudif-p1025-w1-preview-app` contém a aplicação e volume persistente; `cloudif-p1025-w1-preview-web` é sidecar/gateway.
- Produção ativa continua D1 legada/placeholder e não foi alterada.
- Project Config Controller continua `configuration_required` (`review_and_apply_manifest`).
- Gate global no Komodo impede `cloudif_preview_snapshot()` de congelar sidecar/gateway como aplicação. Paperclip retorna `preview_composite_runtime_requires_manifest` antes de qualquer efeito.
- Prova: tentativa sintética de snapshot retornou HTTP 409, `candidate_count=0`, sem imagem H, W1/D1 intactos.

### Remediação segura

Definir manifest completo do runtime composto (incluindo política do volume) antes de habilitar H. Depois executar o primeiro ciclo moderno W1→H→mesma H em P pelo proprietário. Não usar o snapshot genérico e não inferir automaticamente o tratamento dos dados persistentes.
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

## Resíduos de host relevantes após remediações

### Forja

- Agenda: históricos P3/P6 permanecem preservados e Offline; P7 ativa conforme.
- Cadales: W2/H2 antigos removidos; P2 ativa legada preservada.
- CPUHub: D2–D5 removidos; W2/H2–H5/P2/P3 sem stages ativos; P5 é a única Produção ativa.
- Laboratório: H11/H13/P5 residuais desativados; somente W1 e P12 consomem runtime de aplicação relevante.
- Paperclip: canary/rollback antigos removidos pela remediação concorrente; W1 composto app+gateway preservado.
- SGREP: resíduos exited de smoke/rollback removidos; W1 source-linked preservado.
- SilviPro: D2 parado; W1 contínuo e P1 ativa preservados.

### Hospedagem

Containers Agenda antigos exited ainda podem existir como evidência/rollback; não há indicação de consumo ativo. Qualquer remoção definitiva exige nova prova de ausência de referência em systemd/Nginx/Portal.

## Prioridade atual depois da auditoria/remediação

1. **Gate humano — Laboratório:** executar novo W1→H→mesma H em P; P12 permanece legado até esse ciclo.
2. **Gate de manifest — Paperclip:** definir runtime composto completo (app/gateway/volume) antes de H; snapshot genérico está bloqueado com segurança.
3. **Gate humano — Cadales:** próximo H→P deve usar o contrato atual; P2 permanece legado saudável até lá.
4. **Gate humano — CPUHub:** próximo H→P deve usar o contrato atual; P5 permanece legado saudável até lá.
5. **Gate humano — SilviPro:** próximo H→P deve usar o contrato atual; P1 importada como legado permanece ativa.
6. **Gap funcional — SGREP v2:** Terminal source-linked ainda precisa de contrato explícito; Preview está saudável/read-model conforme.
7. **N/A — MSHA:** permanece draft sem runtime; entrar diretamente no padrão quando houver pedido de publicação.
8. **Referência — Agenda Única:** manter como projeto de regressão para o padrão completo same-instance.
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
