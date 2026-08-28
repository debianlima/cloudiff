# Estado — 2026-08-28 — contrato v59

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a correção desta unidade não altera HTML, CSS, JS visual, textos, botões ou layout.
- O link congelado `Visão geral` (`?tab=resumo`) deve produzir o mesmo painel acadêmico canônico servido na raiz do Portal; o renderer administrativo legado não é contrato visual válido para esse alias.
- A promoção produtiva da correção `Visão geral` está homologada: live hash `1ae42e1e...`, `current` no candidato, `previous` no baseline `4407bd7c...`, raiz/alias/navigation equivalentes e verificador residente `errors=0`.
- Faro é o nó CloudIFF de papel `edge`; seu perfil deseja `portal-host`, mas o cutover do Portal ocorre somente após onboarding Faro e portões de portal shadow.
- O onboarding Faro está aceito: 4 vCPU online, identidade própria, PKI/NATS individual, agent não-root, heartbeat direto para Hospedagem, reconciliação/resiliência e rollback já possuem evidência mecânica.
- O heartbeat atual do Faro observa capabilities `inventory`, `health`, `telemetry-host`, `portal-host` e `agent-auto-update`; `build` e `runtime` continuam excluídas do perfil Faro.
- O caminho crítico Faro é `10.62.91.5 -> NATS 10.62.92.7:14222 -> cloudiff-control -> PostgreSQL`; Forja e Maurício não participam do heartbeat crítico.
- Releases de agent-skills permanecem imutáveis; o runtime Faro continua na release instalada `cloudiff@0.1.4`, enquanto a skill de projeto usada nesta unidade é `cloudiff@0.1.17`.

## Decisões superadas
- Salto obrigatório via `172.16.0.1` para acessar máquinas do laboratório — superado em 28/08/2026 pela nova orientação da TI comunicada pelo operador; acesso operacional passa a ser direto pelo conector Labiff, mantendo pfSense/MikroTik apenas como equipamentos de rede quando necessário.
- Faro bloqueado por `2/4 vCPU` — superado em 26/08/2026 após a TI ampliar a VM e o SO observar CPUs `0-3`.
- `portal-host` apenas desejada/não observada — superado pelo heartbeat PostgreSQL atual, que já anuncia `portal-host`; isso não equivale a cutover do Portal.
- Confiar apenas na árvore de uma release de skills já existente como prova do artefato recebido — superado na v45 pelo gate do TAR recebido.

## Decisões humanas pendentes
- Nenhuma decisão humana adicional para aceitar o nó Faro.
- Cutover definitivo do Portal para Faro permanece uma unidade posterior e deve respeitar os portões de portal shadow/FrozenPortalInterface; não foi executado implicitamente nesta unidade.

## Decisões fechadas nesta emenda
- `project.created` e `project.membership.changed` são duráveis no Portal: SQLite `reconcile_requests` + marcador com fsync/replace atômico + partição/retry/dead-letter.
- O consumidor autoritativo desses eventos continua sendo `cloudif-reconcile-worker.py`; `cloudiff-control` C++ live `0.15.0-shadow` assina somente `cloudiff.v2.node.observed` e não contém os eventos de projeto.
- Não se declara reconciliação de projeto migrada para C++ enquanto não existir consumidor explícito com os mesmos eventos, semântica de partição/retry e efeitos externos equivalentes.

## Pendências técnicas não humanas
- Dois `project.membership.changed` históricos (05/08 e 07/08) permanecem `dead_letter`; o registro preservou apenas `RuntimeError`, sem detalhe de causa. Não reenfileirar sem revisão separada dos efeitos atuais.
- A migração de reconciliação de projeto para C++ continua pendente do outro fluxo; `cloudiff-control` atual não é substituto do worker Python.
- A migração dos efeitos W/H/P para C++ também permanece pendente; planner/policy não substitui deploy/rollback/status duráveis.
- Procedência exata de alguns binários live (`RuntimeExecutor` v17/v24 e publisher NPM v10) permanece `NAO DECLARADO`.
- LegacyRetirement continua separado e destrutivo somente com gates próprios.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `T-013-project-events-cpp-reconciliation`, concluída; nenhuma zona de exclusão permanece ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.17` — skill raiz; L026 homologado nesta unidade.
- `desenvolvedor-de-software@14` — método PGH.
- `github-incremental-reconciliation@7` — reconciliação incremental de skill/catálogo.
- `governanca-ontologica-de-skills@1.0.4` — governança da versão da skill.
- `telemetry-data-visualization@2` — macro global; coletor executável indisponível.
- `platform-engineering` / `operational-ui-truth` — prova de produtor, fila, consumidor e efeito observado.

## Falhas de portão por tipo de entrada
- `reconciliacao`: presença de `cloudiff-control` C++ ativo não cobre `project.created`/`project.membership.changed`; o subscriber é apenas `cloudiff.v2.node.observed`.
- `operacao`: dois dead-letters históricos de membership não preservam detalhe suficiente além de `RuntimeError`; replay automático não é seguro sem revisão separada.

## Divergências da última reconciliação
### Corrigidas
- Entrada 1531 registra o caminho real Hospedagem: produtores → SQLite/marker → worker Python → efeitos externos/status durável.
- Entrada 1532 impede overclaim de migração C++: o source/control live é verificado como node-observation only e o worker Python permanece autoritativo.
- Fila atual não possui itens `queued/waiting_retry/running`; os dois dead-letters históricos foram preservados como dívida operacional, não confundidos com backlog atual.
- `cloudiff@0.1.17` registra L026; nenhum HTML/CSS/JS visual foi alterado (`VISUAL_DIFF=NO`).

### Pendentes de autorização ou capacidade
- Reanalisar os dois dead-letters antes de qualquer replay, pois replay produz efeitos em Forgejo/Komodo/tenant/onboarding.
- O `main` do Cloudiff continua separado do branch auditável; nenhum merge foi inferido.

## Entradas aceitas nesta unidade
- 1531 `docs/reconciliation/project-events-cpp-reconciliation-v59.json` — evidência live de produtores/fila/worker/control C++.
- 1532 `tests/test_project_events_cpp_reconciliation_evidence.py` — gate contra overclaim de consumidor C++.
- 179 `skills/cloudiff/SKILL.md` — `cloudiff@0.1.17`, L026 homologado.
- 2 `competencias.yaml` — skill raiz reconciliada em `0.1.17`.
- 9 `estado.md` — snapshot v59.
- 10 `manifesto.yaml` — contrato v59 e zona liberada.

## Próxima unidade
- Auditar os dois `project.membership.changed` históricos em dead-letter por canais somente leitura; só propor replay após reconstruir a causa e provar que os efeitos atuais são idempotentes.
- Continuar a auditoria de agentes C++ recém-migrados que aparecerem no branch, sempre confrontando consumidor/efeito live e sem alterar `FrozenPortalInterface`.
