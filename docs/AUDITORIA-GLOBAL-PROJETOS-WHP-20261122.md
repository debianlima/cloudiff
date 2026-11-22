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
| `cadales` | W2 saudável | **não**: bind `0599c798...`, Komodo `ad8e67c` | P2 saudável | não comprovado; fluxo antigo | sem P histórica moderna ativa | **NÃO CONFORME — Preview atrasado** |
| `cpuhub` | W2 saudável | alinhado (`97af1e3...`) | P5 saudável | não comprovado; fluxo antigo | H3 ainda `awaiting_homologation`; P2/P3 Offline | **PARCIAL / LEGADO** |
| `laboratorio-de-hardware` | W1 saudável após remediação | alinhado `3b399e9` | P12/alias saudáveis | **não** historicamente: H13 `dep_51a7...` → P12 `dep_210f...` | H11/H13/P5 agora Offline; snapshots preservados | **PARCIAL — aguarda novo H→P humano** |
| `msha` | não configurado | n/a | nenhuma | n/a | nenhum runtime de publicação | **DRAFT / N/A** |
| `paperclip` | W1 responde 200, app informa falha de inicialização | hash `dfcaaf8...` alinhado | D1 legado é placeholder “primeiros passos” | n/a | Preview fora do contrato moderno | **BLOQUEADOR / LEGADO** |
| `sgrep-v2` | W1 real existe, mas read-model diz “não configurado” | source link `f29f752...` coincide com Komodo | nenhuma | n/a | runtime Preview fora do fluxo do Portal | **DRIFT DE READ-MODEL** |
| `silvipro` | Portal diz não configurado; W1 redireciona ao Portal | não comprovado | D1 legado é placeholder “primeiros passos” | n/a | D2/P1 containers ativos fora do modelo atual | **BLOQUEADOR / LEGADO** |

## 1. Agenda Única — conforme

- Public number 1020.
- Preview fixo W3: `1020-w3-preview.cloudiff.duckdns.org`, HTTP 200.
- Preview Git: `1841612...`, status `synced`.
- Produção ativa P7 e alias `agendaunica.cloudiff.duckdns.org`: HTTP 200, mesma revisão observada.
- H7 e P7 usam o mesmo `deployment_id` `dep_19bc037d073bf2418f9050c7` e o mesmo snapshot `snap_29103714e0b1ac96c11b8955`.
- P6 e P3 terminam Offline; P6 possui reidratação histórica comprovada; P2 é legado Offline.

Nota importante: labels Docker dos containers promovidos podem ainda indicar `homologation` porque labels são imutáveis. **Não recriar containers só para alterar label**; a identidade preservada é justamente a prova do H→P in-place.

## 2. Cadales — Preview fixo não acompanha Forgejo

- Public number 1022; W2 e P2 respondem HTTP 200.
- Bind ativo de `/var/www/html` está no commit `0599c7985678491878fe987da2ead65d957d1371`.
- Komodo/Forgejo anuncia `ad8e67c` como `latest_hash`.
- O read-model do Portal informa `synced`, portanto há também um falso positivo de sincronização.
- Stack Komodo ainda espera `docker-compose.yml` no Git e retorna `deploy_status=failed`; o Preview continua funcionando por mecanismo legado/bind.
- H2/P2 não possuem metadados `sameInstancePromotionRequired`/`homologationDeploymentId`; não existe evidência suficiente para afirmar promoção da mesma instância.

### Remediação segura

1. corrigir a fonte de sincronização do W2 para o `main` atual sem trocar URL/slot;
2. corrigir o read-model para não declarar `synced` quando checkout e `latest_hash` divergem;
3. remover a expectativa legada de `docker-compose.yml` do caminho gerenciado, sem adicionar infraestrutura ao repositório da aplicação;
4. somente no próximo ciclo gerar nova H pelo fluxo atual e promover a mesma instância para P; não reescrever P2 ativa sem candidato testado.

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

## 7. SGREP v2 — Preview existe fora do read-model do fluxo

- Projeto está `draft`, public number 1026.
- `project_preview_source_links` registra W1 `online`, source commit `f29f752f2aadbdad46b46570b29b2895007fb6cb`, bind readonly e dados isolados.
- Containers `cloudif-sgrep-v2-preview-app`, `preview-db`, `preview-sat` e gateway `cloudif-p1026-w1-preview-web` estão ativos.
- A URL W1 responde 307 para `/login?path=/` e chega a HTTP 200 após autenticação/login flow.
- Mesmo assim, `release_flow_status` devolve `configured=false`.
- `public_external_verified=0` no source link.

### Remediação segura

Reconciliar `preview_status/release_flow_status` com `project_preview_source_links` e decidir explicitamente se o projeto continua draft ou passa a publicado. Não recriar o Preview existente para corrigir apenas o read-model.

## 8. SilviPro — Produção placeholder e rotas inconsistentes

- Public number 1002.
- D1 é a única publicação registrada como ativa.
- Alias `silvipro.cloudiff.duckdns.org` responde 200, porém mostra `silvipro · primeiros passos` / `Seu projeto está publicado.` — placeholder da plataforma.
- `1002-d1` retorna 502.
- W1 e D2 redirecionam para `/cloudiff/portal/`, não para a aplicação.
- Containers `cloudif-p1002-d2-web` e `cloudif-p1002-p1-publication-web` estão running/healthy, mas não correspondem ao modelo de release atual do banco.
- O corpo de P1/D2 difere do alias estável, comprovando drift de roteamento/conteúdo.

### Remediação segura

Primeiro mapear commit/origem de D2/P1 e provar rollback; depois restaurar um W1 de aplicação real. Não parar D2/P1 até entender se alguma rota interna ainda depende deles. Só então criar H moderna e substituir o placeholder D1.

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
