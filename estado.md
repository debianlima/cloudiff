# Estado — 2026-08-31 — contrato v45

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; nenhuma mudança de Portal/UI, navegação ou rotas de usuário foi feita nesta unidade.
- Faro é o nó CloudIFF de papel `edge`; seu perfil deseja `portal-host`, mas o cutover do Portal ocorre somente após onboarding Faro e portões de portal shadow.
- O onboarding Faro está aceito: 4 vCPU online, identidade própria, PKI/NATS individual, agent não-root, heartbeat direto para Hospedagem, reconciliação/resiliência e rollback já possuem evidência mecânica.
- O heartbeat atual do Faro observa capabilities `inventory`, `health`, `telemetry-host`, `portal-host` e `agent-auto-update`; `build` e `runtime` continuam excluídas do perfil Faro.
- O caminho crítico Faro é `10.62.91.5 -> NATS 10.62.92.7:14222 -> cloudiff-control -> PostgreSQL`; Forja e Maurício não participam do heartbeat crítico.
- Releases de agent-skills permanecem imutáveis; o runtime Faro continua na release instalada `cloudiff@0.1.4`, enquanto a skill de projeto usada nesta unidade é `cloudiff@0.1.5`.

## Decisões superadas
- Faro bloqueado por `2/4 vCPU` — superado em 26/08/2026 após a TI ampliar a VM e o SO observar CPUs `0-3`.
- `portal-host` apenas desejada/não observada — superado pelo heartbeat PostgreSQL atual, que já anuncia `portal-host`; isso não equivale a cutover do Portal.
- Confiar apenas na árvore de uma release de skills já existente como prova do artefato recebido — superado na v45 pelo gate do TAR recebido.

## Decisões humanas pendentes
- Nenhuma decisão humana adicional para aceitar o nó Faro.
- Cutover definitivo do Portal para Faro permanece uma unidade posterior e deve respeitar os portões de portal shadow/FrozenPortalInterface; não foi executado implicitamente nesta unidade.

## Decisões fechadas nesta emenda
- Faro atende ao perfil de recurso `4 vCPU / 8 GiB configurados / 200 GiB disco`; os três resource gates estão `pass`.
- `FARO-T19` passou e a etapa `acceptance` mudou de `partially_verified` para `verified`.

## Pendências técnicas não humanas
- O host Faro mantém `fwupd-refresh.service` falho por indisponibilidade de egress para o serviço externo; o verificador residente retorna `errors=0 warnings=1`. Isso não afeta o runtime CloudIFF/NATS.
- O inventário de máquina ainda precisa refletir Docker/cAdvisor presentes no Faro; máquina vence o inventário e a reconciliação é a próxima correção de ambiente desta mesma entrega.
- Permanecem 21 entradas `pendente` e 5 `preexistente` no contrato v45 fora desta unidade; a liberação global do projeto deve selecionar quais delas são release-blocking antes de declarar release final.
- LegacyRetirement continua separado e qualquer retirada destrutiva exige seus próprios gates e autorização final.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — vazio; o bloco concluído `faro-cloudiff-release` foi removido na reconciliação de 31/08/2026 porque não representava trabalho vivo e tinha zona de exclusão vazia.

## Competências ativas nesta unidade
- `cloudiff@0.1.5` — skill raiz carregada no início da unidade.
- `desenvolvedor-de-software@14` — método PGH.
- `github-incremental-reconciliation@7` — reconciliação incremental antes de normalização/release.
- `governanca-ontologica-de-skills@1.0.4` — preservação do fecho de skills.
- `telemetry-data-visualization@2` — macro global.
- `network-ssh-operations@1` — primeiro salto pfSense e validação multi-host.

## Falhas de portão por tipo de entrada
- `infraestrutura/Faro`: documentos de perfil/reserva ainda registravam 2 vCPU apesar do runtime já observar 4; reconciliados para o estado real.
- `agente/Faro`: evidências antigas omitiam `portal-host`; o PostgreSQL atual comprovou capability e os artefatos foram reconciliados.
- `verificação`: um gate TLS agregado usava o exit code de `openssl s_client` após EOF; a cadeia estava válida (`Verify return code: 0`). O gate foi corrigido para validar a evidência de cadeia, não o encerramento do cliente de diagnóstico.

## Divergências da última reconciliação
### Corrigidas
- `manifesto.yaml.trabalho_compartilhado`: removido bloco concluído `faro-cloudiff-release` (concluído em 26/08/2026, zona de exclusão vazia); fonte canônica voltou a representar apenas trabalho vivo.
- `config/faro-node-profile.json`: `observed_resources.vcpu=4`, `resource_gates.vcpu=pass`, recursos `satisfied`.
- `config/faro-node-reservation.json`: recursos observados reconciliados com heartbeat atual e `vcpu=pass`.
- `config/faro-validation-01-discovery.json`: CPU atual e `portal-host` observada.
- `config/faro-validation-04-agent-heartbeat.json`: heartbeat atual registra `cpu_count=4` e `portal-host`.
- `config/faro-validation-06-acceptance.json`: `verification_status=verified` e `FARO-T19=passed`.

### Pendentes de autorização ou capacidade
- Nenhuma pendência de capacidade para Faro.
- Portal cutover permanece deliberadamente fora desta unidade.

## Entradas aceitas nesta unidade
- 9 `estado.md` — snapshot atual do contrato v45.
- 10 `manifesto.yaml` — estados e trabalho compartilhado reconciliados.
- 118 `config/faro-validation-01-discovery.json` — descoberta atualizada com 4 vCPU/portal-host observada.
- 121 `config/faro-validation-04-agent-heartbeat.json` — observed state atual reconciliado.
- 123 `config/faro-validation-06-acceptance.json` — etapa final `verified`.
- 124 `tests/test_faro_validation_model.py` — seis etapas verificadas.
- 126 `config/faro-node-reservation.json` — recurso vCPU aceito.
- 131 `tests/test_faro_node_preparation.py` — reserva/resource gate atualizados.
- 140 `config/faro-node-profile.json` — perfil satisfeito.
- 165 `tests/test_faro_profile.py` — gate 4 vCPU atualizado.

## Portões Faro
- `FARO_RUNTIME_GATE=PASS`: 4 vCPU, agent ativo/enabled, updater timer ativo/enabled, NATS TLS válido, cAdvisor loopback-only e somente SSH exposto externamente.
- `FARO_DB_GATE=PASS`: `node_count=1`, `cpu_count=4`, `portal-host=true`, heartbeat recente.
- `FARO_VALIDATION_MODEL=PASS`: 6 etapas verificadas, nenhuma parcial.
- `FARO_PROFILE=PASS` e `FARO_NODE_PREPARATION=PASS`.
- Suíte oficial: 1008 testes PASS + 1 skip.
- Frozen UI: 3/3 PASS; nenhum arquivo Portal/UI alterado.
- Secret scan, `git diff --check` e higiene `__pycache__`: PASS.

## Próxima unidade
- Reconciliar o inventário descritivo do Faro com Docker/cAdvisor observados.
- Em seguida, calcular o fecho de liberação global do CloudIFF e separar as 21 entradas pendentes em release-blocking versus trabalho posterior.
- Portal shadow/cutover para Faro só inicia depois desse fecho e sem alterar a interface homologada antes dos portões próprios.
