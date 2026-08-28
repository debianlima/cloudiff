# Estado — 2026-08-28 — contrato v58

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a correção desta unidade não altera HTML, CSS, JS visual, textos, botões ou layout.
- O link congelado `Visão geral` (`?tab=resumo`) deve produzir o mesmo painel acadêmico canônico servido na raiz do Portal; o renderer administrativo legado não é contrato visual válido para esse alias.
- A promoção produtiva da correção `Visão geral` está homologada: live hash `1ae42e1e...`, `current` no candidato, `previous` no baseline `4407bd7c...`, raiz/alias/navigation equivalentes e verificador residente `errors=0`.
- Faro é o nó CloudIFF de papel `edge`; seu perfil deseja `portal-host`, mas o cutover do Portal ocorre somente após onboarding Faro e portões de portal shadow.
- O onboarding Faro está aceito: 4 vCPU online, identidade própria, PKI/NATS individual, agent não-root, heartbeat direto para Hospedagem, reconciliação/resiliência e rollback já possuem evidência mecânica.
- O heartbeat atual do Faro observa capabilities `inventory`, `health`, `telemetry-host`, `portal-host` e `agent-auto-update`; `build` e `runtime` continuam excluídas do perfil Faro.
- O caminho crítico Faro é `10.62.91.5 -> NATS 10.62.92.7:14222 -> cloudiff-control -> PostgreSQL`; Forja e Maurício não participam do heartbeat crítico.
- Releases de agent-skills permanecem imutáveis; o runtime Faro continua na release instalada `cloudiff@0.1.4`, enquanto a skill de projeto usada nesta unidade é `cloudiff@0.1.16`.

## Decisões superadas
- Salto obrigatório via `172.16.0.1` para acessar máquinas do laboratório — superado em 28/08/2026 pela nova orientação da TI comunicada pelo operador; acesso operacional passa a ser direto pelo conector Labiff, mantendo pfSense/MikroTik apenas como equipamentos de rede quando necessário.
- Faro bloqueado por `2/4 vCPU` — superado em 26/08/2026 após a TI ampliar a VM e o SO observar CPUs `0-3`.
- `portal-host` apenas desejada/não observada — superado pelo heartbeat PostgreSQL atual, que já anuncia `portal-host`; isso não equivale a cutover do Portal.
- Confiar apenas na árvore de uma release de skills já existente como prova do artefato recebido — superado na v45 pelo gate do TAR recebido.

## Decisões humanas pendentes
- Nenhuma decisão humana adicional para aceitar o nó Faro.
- Cutover definitivo do Portal para Faro permanece uma unidade posterior e deve respeitar os portões de portal shadow/FrozenPortalInterface; não foi executado implicitamente nesta unidade.

## Decisões fechadas nesta emenda
- O `RuntimeExecutor` C++ já possui paridade de **política** para HOMOLOGATION/CANARY/PRODUCTION, mas não paridade de **efeito**: o planner live é side-effect-free e o canary C++ habilita somente TEST/PREVIEW.
- O planner live da Forja é `0.17.0-shadow` e responde `effects_not_enabled_v17`; o branch auditável declara agente `0.36.0-shadow` e source `effects_not_enabled_v18`. Sem procedência do binário live, não se declara o source atual implantado.
- HOMOLOGATION/CANARY/PRODUCTION continuam autoritativos nos executores Python ativos em 18217/18219/18220; não podem ser retirados até o C++ provar estado durável, idempotência, smoke, switch atômico, rollback e health externo equivalentes.

## Pendências técnicas não humanas
- Recuperar a procedência exata dos binários `RuntimeExecutor` live `0.17.0-shadow` e canary `0.24.0-shadow`; commits fonte permanecem `NAO DECLARADO`.
- A migração dos efeitos W/H/P para C++ continua pendente do outro fluxo: planner/policy não substitui deploy/rollback/status com persistência durável.
- Reconciliação C++ de projeto/publicação ainda não possui consumidor equivalente aos eventos duráveis do Portal; o `cloudiff-control` atual é restrito a observação de nó.
- A procedência exata da release live do publisher NPM v10 também permanece `NAO DECLARADO`; o host Maurício já foi reconciliado para 38% de uso de `/`, removendo o antigo bloqueio de capacidade por 91%.
- Permanecem entradas `pendente`/`preexistente` fora desta unidade; LegacyRetirement continua separado e destrutivo somente com gates próprios.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `T-012-runtimeexecutor-cpp-whp`, concluída; nenhuma zona de exclusão permanece ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.16` — skill raiz; L025 homologado nesta unidade.
- `desenvolvedor-de-software@14` — método PGH.
- `github-incremental-reconciliation@7` — reconciliação incremental de skill/catálogo.
- `governanca-ontologica-de-skills@1.0.4` — governança da versão da skill.
- `telemetry-data-visualization@2` — macro global; coletor executável indisponível, medida classificada como `indisponivel`.
- `platform-engineering` / `operational-ui-truth` — prova de runtime, procedência e canal independente de efeitos.

## Falhas de portão por tipo de entrada
- `procedencia`: planner live `0.17.0-shadow` e canary `0.24.0-shadow` não têm commit fonte declarado no histórico disponível; o branch atual reporta `0.36.0-shadow`.
- `runtime`: W/H/P têm policies C++ corretas, mas `/v1/execute` H/P é bloqueado e o canary C++ só admite TEST/PREVIEW; os efeitos continuam nos executores Python.
- `reconciliacao`: `cloudiff-control` continua sem consumo dos eventos de projeto duráveis; T-013 deve auditar esse limite separadamente.

## Divergências da última reconciliação
### Corrigidas
- Entrada 1529 registra a Forja real: planner C++ 0.17 ativo em 18232 loopback, canary C++ 0.24 inativo, executores Python H/C/P ativos em 18217/18219/18220.
- Planos HOMOLOGATION e PRODUCTION retornaram `side_effect_free=true`, políticas corretas e `effects_enabled=false`; `/execute` retornou 409 antes de qualquer efeito.
- Inventário Docker antes/depois permaneceu no mesmo SHA-256 `b755a002...`, provando efeito zero do planner auditado.
- Entrada 1530 impede overclaim: source atual 0.36 não é tratado como live e W/H/P não é marcado migrado enquanto os efeitos duráveis permanecerem no legado.
- `cloudiff@0.1.16` registra L025; nenhum HTML/CSS/JS visual foi alterado (`VISUAL_DIFF=NO`).

### Pendentes de autorização ou capacidade
- Implementação C++ dos efeitos W/H/P pertence ao fluxo de migração e deve chegar com portões equivalentes antes de substituir os serviços Python.
- O `main` do Cloudiff continua separado do branch auditável; nenhum merge foi inferido.

## Entradas aceitas nesta unidade
- 1529 `docs/reconciliation/runtime-executor-whp-parity-v58.json` — evidência live W/H/P e limites de substituição.
- 1530 `tests/test_runtime_executor_whp_parity_evidence.py` — contrato/source/systemd/legado/live cruzados mecanicamente.
- 179 `skills/cloudiff/SKILL.md` — `cloudiff@0.1.16`, L025 homologado.
- 2 `competencias.yaml` — skill raiz reconciliada em `0.1.16`.
- 9 `estado.md` — snapshot v58.
- 10 `manifesto.yaml` — contrato v58 e zona liberada.

## Próxima unidade
- T-013: auditar reconciliação C++ dos eventos `project.created` e `project.membership.changed`, confrontando produtores duráveis do Portal, broker/fila e consumidores atuais; não inventar vínculo no `cloudiff-control` se ele continuar restrito a `node.observed`.
