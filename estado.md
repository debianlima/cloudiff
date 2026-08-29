# Estado — 2026-08-28 — contrato v71

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a correção desta unidade não altera HTML, CSS, JS visual, textos, botões ou layout.
- O link congelado `Visão geral` (`?tab=resumo`) deve produzir o mesmo painel acadêmico canônico servido na raiz do Portal; o renderer administrativo legado não é contrato visual válido para esse alias.
- A promoção produtiva da correção `Visão geral` está homologada: live hash `1ae42e1e...`, `current` no candidato, `previous` no baseline `4407bd7c...`, raiz/alias/navigation equivalentes e verificador residente `errors=0`.
- Faro é o nó CloudIFF de papel `edge`; seu perfil deseja `portal-host`, mas o cutover do Portal ocorre somente após onboarding Faro e portões de portal shadow.
- O onboarding Faro está aceito: 4 vCPU online, identidade própria, PKI/NATS individual, agent não-root, heartbeat direto para Hospedagem, reconciliação/resiliência e rollback já possuem evidência mecânica.
- O heartbeat atual do Faro observa capabilities `inventory`, `health`, `telemetry-host`, `portal-host` e `agent-auto-update`; `build` e `runtime` continuam excluídas do perfil Faro.
- O caminho crítico Faro é `10.62.91.5 -> NATS 10.62.92.7:14222 -> cloudiff-control -> PostgreSQL`; Forja e Maurício não participam do heartbeat crítico.
- Releases de agent-skills permanecem imutáveis; o runtime Faro continua na release instalada `cloudiff@0.1.4`, enquanto a skill de projeto usada nesta unidade é `cloudiff@0.1.27`.

## Decisões superadas
- Salto obrigatório via `172.16.0.1` para acessar máquinas do laboratório — superado em 28/08/2026 pela nova orientação da TI comunicada pelo operador; acesso operacional passa a ser direto pelo conector Labiff, mantendo pfSense/MikroTik apenas como equipamentos de rede quando necessário.
- Faro bloqueado por `2/4 vCPU` — superado em 26/08/2026 após a TI ampliar a VM e o SO observar CPUs `0-3`.
- `portal-host` apenas desejada/não observada — superado pelo heartbeat PostgreSQL atual, que já anuncia `portal-host`; isso não equivale a cutover do Portal.
- Confiar apenas na árvore de uma release de skills já existente como prova do artefato recebido — superado na v45 pelo gate do TAR recebido.

## Decisões humanas pendentes
- Nenhuma decisão humana adicional para aceitar o nó Faro.
- Cutover definitivo do Portal para Faro permanece uma unidade posterior e deve respeitar os portões de portal shadow/FrozenPortalInterface; não foi executado implicitamente nesta unidade.

## Decisões fechadas nesta emenda
- T-033 homologou no repositório observabilidade causal para retry/dead-letter do reconcile worker sem deploy live.
- O schema acrescenta `last_error_stage`, `last_error_upstream`, `last_error_status`, `last_error_code` e `last_error_detail` por migração incremental; `last_error_type` permanece compatível.
- Membership distingue `membership.forgejo`/`forja-agent` e `membership.komodo`/`komodo-agent`; runtime usa `runtime.reconcile`/`runtime-reconciler`.
- Dead-letter preserva `error_type` e `secrets_exposed=false`, acrescentando `diagnostic`. Sucesso limpa os campos `last_error_*`.
- Sanitização remove Bearer, assignments sensíveis e URL userinfo. Exceções genéricas nunca persistem `str(exc)`, somente o tipo.
- Política operacional não mudou: `max_attempts=5`, `lease=45s`, particionamento e backoff preservados.
- SQLite temporário real: 7/7 PASS; T-016/T-016R: 8/8 PASS; Portal: 1038/1038; validator/mirrors/secret scan PASS; `VISUAL_DIFF=NO`.
- T-033R permanece BLOCKED: deploy/restart live do worker é frente effectful separada e não foi autorizado pelo BOT.

## Pendências técnicas não humanas
- T-033R BLOCKED: deploy do worker/client enriquecidos exige gate effectful separado e autorização adequada.
- T-034R BLOCKED: hardening/rotação do `NPM data/keys.json` requer autorização humana.
- T-036R BLOCKED: corrigir/deployar o contrato do UI security gate requer decisão humana.
- T-028 BLOCKED: falta identificar o nó/cluster Proxmox do pfSense para ler lifecycle host-side.
- T-029R BLOCKED: implantação HA pfSense depende de autorização humana, inventário de IPs, WAN/TI e nó Proxmox.
- T-035 READY: warning HTTP/2 NPM pode ser tratado estaticamente; reload fica separado.
- T-022/T-023/T-024/T-025/T-032 permanecem dependentes de wiring/releases externas.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `T-033-deadletter-observability`, concluída; nenhuma zona de exclusão permanece ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.27` — skill raiz; L036 homologado.
- `desenvolvedor-de-software@14` — método PGH.
- `github-incremental-reconciliation@7` — reconciliação incremental.
- `governanca-ontologica-de-skills@1.0.4` — governança.
- `telemetry-data-visualization@2` — macro global; coletor indisponível.

## Falhas de portão por tipo de entrada
- `backend-integracao`: fixture inicial de migração era irrealmente incompleto; corrigido para representar o schema pre-T-033 antes do aceite.
- `repository-validator`: `py_compile` criou `__pycache__`, fixture tinha URL autenticada sintética literal e README tinha blank line extra; todos removidos/corrigidos antes do aceite.

## Divergências da última reconciliação
### Corrigidas
- Worker e mirror byte-idênticos; client e dois mirrors byte-idênticos.
- Evidência v71 e teste SQLite real cobrem retry, dead-letter, sanitização, migração e limpeza no sucesso.
- Compatibilidade histórica T-016/T-016R preservada.
- `cloudiff@0.1.27` registra L036; `VISUAL_DIFF=NO`.

### Pendentes de autorização ou capacidade
- T-033R não deployado; produção continua sob o worker anterior até gate effectful separado.

## Entradas aceitas nesta unidade
- 1558 `docs/reconciliation/reconcile-deadletter-observability-v71.json`.
- 1559 `tests/test_reconcile_deadletter_observability.py`.
- 179 `skills/cloudiff/SKILL.md` — `cloudiff@0.1.27`, L036.
- 2 `competencias.yaml` — skill raiz 0.1.27.
- 9 `estado.md` — snapshot v71.
- 10 `manifesto.yaml` — contrato v71 e zona liberada.

## Próxima unidade
- T-035: localizar e preparar correção estática do warning HTTP/2 NPM; sem reload/deploy live.
