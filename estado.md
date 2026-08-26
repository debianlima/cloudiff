# Estado — 2026-08-26 — contrato v44

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; esta unidade não altera Portal/UI, navegação, rotas de usuário ou comportamento visual homologado.
- Faro `10.62.91.5` está aceito como node `edge` com `inventory`, `health`, `telemetry-host`, `portal-host` e `agent-auto-update`; `build` e `runtime` continuam excluídos.
- O requisito de capacidade do Faro permanece 4 vCPU / 8 GiB configurados / 200 GiB de disco; em 26/08/2026 o SO passou a observar 4 vCPU online (`0-3`).
- O cutover do Portal continua separado do aceite do node e só ocorre após os gates de portal-shadow previstos no perfil; nenhum cutover foi executado nesta unidade.
- Monitoramento padrão do Faro permanece cAdvisor `v0.57.0`, image ID pinado e exposição somente em `127.0.0.1:18081`.
- `cloudiff@0.1.4` é a skill de projeto ativa; o princípio “competência acrescenta acesso; não retira identidade” permanece preservado e nenhum algoritmo nativo foi alterado.

## Decisões superadas
- “Faro possui 2/4 vCPU e não pode concluir o aceite” — superada pela observação viva de 4 vCPU em 26/08/2026.
- `apply` do WebDev sempre reiniciar `cloudiff-webdev.service` — permanece superada pela idempotência homologada na v44.
- Link operacional principal apenas `http://10.62.91.2:17900/` — permanece superado pelo HTTPS fixo VPN-only, mantendo o link direto apenas como canal interno restrito.

## Decisões humanas pendentes
- Nenhuma nova decisão humana nesta unidade.

## Pendências técnicas não humanas
- Faro continua com egress Internet filtrado; `fwupd-refresh.service` permanece warning por timeout LVFS, sem afetar CloudIFF/NATS/heartbeat.
- Cinco arquivos V1 continuam `preexistente` por links Markdown quebrados.
- LegacyRetirement continua bloqueado pela integridade remota do backup principal `pre-v2-20260820` enquanto o servidor de backup estiver indisponível.
- Acesso direto Hospedagem → `10.68.128.253` permanece filtrado; `.253` responde via salto por `10.68.128.252`.
- Portal-shadow/cutover para Faro é uma unidade futura separada; o aceite do node não autoriza migração automática da interface.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `faro-final-acceptance-v46`, concluída em `2026-08-26T13:11:46-03:00`, sem zona de exclusão ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.4` — skill raiz do projeto.
- `desenvolvedor-de-software@14` — método PGH.
- `github-incremental-reconciliation@7` — reconciliação antes de normalização/release.
- `governanca-ontologica-de-skills@1.0.4` — fecho/identidade das competências.
- `telemetry-data-visualization@2` — macro global da unidade.
- `platform-engineering` e `release-it` — Docker/systemd, idempotência e preservação do agente.
- `network-ssh-operations` — verificação SSH/NATS entre Faro e Hospedagem.

## Competências instaladas/atualizadas para unidades futuras
- Nenhuma; a unidade somente reconciliou estado físico e evidência já coberta por `cloudiff@0.1.4`.

## Falhas de portão por tipo de entrada
- Suíte oficial, primeira execução: erro transitório no `tearDownClass` de `test_multiservice_build_broker` ao remover diretório temporário; teste isolado passou 8/8 e o rerun integral passou 1008 testes + 1 skip. Classificado como flake ambiental não reproduzido, sem alteração de código para mascará-lo.
- Gates específicos do Faro: nenhuma reprovação após a reconciliação de capacidade.

## Divergências da última reconciliação
### Corrigidas
- Inventário residente do Faro corrigido de 2 para 4 vCPU e RAM observada atualizada; máquina real prevaleceu sobre o arquivo descritivo.
- `debianlima/dotfiles` remoto avançou para `5afcbb601db7cbcc5e51d110e05b6cc2592cab9d`; clone do Faro foi alinhado e o verificador residente atualizado para o commit reconciliado.
- `config/faro-node-profile.json` passou de `partially-satisfied` para `satisfied`, com gate de CPU `pass`.
- `config/faro-node-reservation.json` passou a registrar 4 vCPU e `observedAt=2026-08-26T13:03:45-03:00`.
- `config/faro-validation-06-acceptance.json` passou de `partially_verified` para `verified`; `FARO-T19` agora está `passed:resource-profile-satisfied-4-of-4-vcpu`.
- cAdvisor foi validado duas vezes com o instalador v45: mesmo container ID, mesmo image ID pinado, API reportando 4 cores e bind loopback preservado.
- `cloudiff-v2-agent.service` preservou o mesmo PID durante as duas execuções do instalador.
- Control-plane/PostgreSQL confirmou `node_count=1`, mesmo node_id do Faro, role `edge`, capabilities esperadas e `observed_at=2026-08-26T13:03:45-03:00`.

### Pendentes de autorização ou capacidade
- Nenhum bloqueio de CPU permanece no Faro.
- Egress externo/LVFS do Faro continua pendência técnica independente do aceite CloudIFF.

## Entradas revalidadas/aceitas nesta unidade
- 123 `config/faro-validation-06-acceptance.json` — aceite final promovido para `verified`.
- 124 `tests/test_faro_validation_model.py` — modelo atualizado para 6/6 estágios verificados e `T19=passed`.
- 126 `config/faro-node-reservation.json` — recursos/heartbeat reconciliados.
- 131 `tests/test_faro_node_preparation.py` — gate de recurso agora exige CPU `pass` e 4 vCPU observadas.
- 140 `config/faro-node-profile.json` — perfil observado satisfeito.
- 165 `tests/test_faro_profile.py` — prova 4/4 vCPU e gates de recurso `pass`.
- 9 `estado.md` — snapshot desta unidade.

## Portões v46
- `DELTA_INVENTORY=PASS` e `LEARNING_PRESERVED=PASS` para o delta 2→4 vCPU; nenhuma normalização destrutiva aplicada.
- Faro `/opt/agentes/verificar.sh`: `errors=0 warnings=1`; warning único `fwupd-refresh.service` já classificado como egress externo.
- `FARO_PROFILE=PASS` — desired 4 vCPU/8 GiB/200 GiB; observed 4 vCPU e gates `pass`.
- `FARO_NODE_PREPARATION=PASS`.
- `FARO_VALIDATION_MODEL=PASS` — verified=6, partial=0, T19=passed.
- `FARO_STANDARD_MONITORING_CONTRACT=PASS`.
- `FARO_NATS_FIREWALL_MODEL=PASS`.
- Monitoramento vivo: cAdvisor idempotente, API cores=4, agent preservado.
- Heartbeat E2E: NATS acessível; PostgreSQL observed state com node_count=1 e timestamp recente.
- Suíte oficial v46: 1008 testes PASS + 1 skip.
- Nenhum arquivo de Portal/UI foi alterado nesta unidade.

## Telemetria PGH
- `telemetria_inicio`: `2026-08-26T13:05:17-03:00` — início da unidade versionada v46.
- `telemetria_fim`: `2026-08-26T13:11:46-03:00` — fechamento do snapshot; tempo decorrido é derivado, não horas humanas.
- cliente/agente: `WORK-SSH`; skill de projeto: `cloudiff@0.1.4`; macro: `telemetry-data-visualization@2`.
- máquinas observadas: `faro` (capacidade/monitoramento/agente), `hospedagem` (NATS/control-plane/PostgreSQL) e `forja` (testes Git v46).
- tokens/custo do cliente: `indisponivel`; nenhuma estimativa foi promovida a observado.

## Próxima unidade
- O node Faro está homologado quanto a onboarding, capacidade, monitoramento, agent/heartbeat e resiliência.
- Próximo trabalho elegível: executar os gates de portal-shadow antes de qualquer cutover, ou reconciliar o egress externo do Faro como pendência independente. Nenhuma migração de Portal deve ocorrer automaticamente.
