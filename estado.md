# Estado — 2026-08-25 — contrato v42

## Decisões vigentes
- CloudIFF V1/Python e V2/C++23 continuam um único projeto reconciliado incrementalmente.
- `FrozenPortalInterface` permanece requisito mestre: nenhum trabalho v42 alterou interface gráfica, navegação ou comportamento visual homologado.
- Skill raiz produzida nesta unidade é `cloudiff@0.1.3`, com L012 homologado: material privado do certificado servidor NATS não é distribuído a agentes; agentes usam certificado cliente próprio + CA confiável + hostname esperado.
- Faro definitivo é `10.62.91.5`, role `edge`, Ubuntu Server 26.04 x86_64, VM KVM.
- Faro usa node_id próprio, credencial NATS individual, chave privada gerada no próprio host, certificado cliente Agent PKI e agent `0.36.0` não-root.
- Faro publica diretamente para `10.62.92.7:14222`; heartbeat não depende de Forja/Maurício.
- Requisito prescritivo de recursos continua 4 vCPU, 8 GiB RAM e 200 GiB disco. O ambiente observado vence apenas o inventário, não o requisito.
- OpenCode/outro agente não é instalado sem autorização explícita.

## Decisões superadas
- Faro como host inexistente/sem SSH — superado; host real e SSH foram homologados.
- Reserva Faro com `nodeOperational=false`, `sshAvailable=false`, `csrSigned=false`, `heartbeatE2E=false` — superada pela reserva v2 observada.
- Caminho Faro→NATS classificado como bloqueado — superado por TCP aberto, contador de firewall para `10.62.91.5` e heartbeat E2E PostgreSQL.
- RAM em “provider-confirmation-required” — superada por DMI de 8 GB; MemTotal guest permanece ~7,25 GiB observável por overhead.
- R14 sem executor runtime — superado por `cloudiff-reconcile` C++ com decisões determinísticas.
- Skill `cloudiff@0.1.2` — substituída por `0.1.3` após homologação L012; recarga obrigatória antes da próxima unidade.

## Decisões humanas pendentes
- Nenhuma nova decisão humana. O requisito de 4 vCPU já foi decidido pelo operador e não será rebaixado automaticamente.

## Pendências técnicas não humanas
- Faro possui 2 vCPU observadas e requer 4 vCPU. Isto bloqueia `config/faro-validation-06-acceptance.json` e o aceite final do node para cargas que exigem o perfil completo, incluindo Portal.
- `fwupd-refresh.service` no Faro falha por timeout de egress para `cdn.fwupd.org`; CloudIFF interno, DNS, HTTPS interno, NATS e heartbeat estão funcionais. Warning registrado no inventário residente.
- Containers/telemetria de container permanecem indisponíveis no Faro porque Docker/cAdvisor/monitoramento padrão ainda não foram implantados.
- Cinco arquivos V1 continuam `preexistente` por links Markdown quebrados.
- LegacyRetirement e instalador de monitoramento padrão continuam declarados e não gerados.
- Backup principal `pre-v2-20260820` continua sem integridade remota completa enquanto o servidor de backup permanecer fora da rede; remoção destrutiva de legacy continua bloqueada.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `faro-onboarding-v42`, concluída, sem zona de exclusão ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.2` — skill ativa durante a execução da v42; produziu candidata `0.1.3` após homologação L012.
- `desenvolvedor-de-software@14` — método de projeto.
- `github-incremental-reconciliation@7` — reconciliação incremental.
- `platform-engineering` no commit fixado — systemd/runtime/onboarding.
- `distributed-agent-control@1` — identidade, heartbeat, reconciliação e resiliência.
- `release-it@1.4.0` — updater assinado e rollback.
- `network-ssh-operations@1` — DNS, NATS, rotas e gates positivos/negativos.
- `telemetry-data-visualization@2` — macro global.

## Competências instaladas para unidades futuras
- `cloudiff@0.1.3` — precisa ser recarregada antes da próxima unidade.

## Falhas de portão por tipo de entrada
- `infraestrutura`: Faro inicialmente tinha apenas 2 vCPU para requisito 4; gap permanece aberto e bloqueia aceite final.
- `rede`: DNS inicial do Faro não tinha resolver global; corrigido com `systemd-resolved` usando `10.62.91.1`, com rollback testado nas tentativas intermediárias.
- `pki`: enrollment falhou primeiro fora de `PYTHONPATH=/srv/cloudif/lib` e sem env do machine-controller; nenhuma emissão ocorreu até usar o runtime canônico. Emissão final serial 100B PASS.
- `agente`: primeiro bootstrap detectou dependência dinâmica ausente; updater falhou fechado sem reboot/loop. Preflight posterior mostrou `MISSING_COUNT=0` e 0.36 ativou com `NRestarts=0`.
- `reconciliacao`: R14 permaneceu não verificado até build/test de `cloudiff-reconcile`; depois passou em Debug+ASan/UBSan e Release, zero warnings.
- `ambiente`: `fwupd-refresh` continua warning externo por egress LVFS indisponível; não foi ocultado nem desabilitado.
- `teste-global`: primeira execução v42 falhou apenas em `TemporaryDirectory.cleanup()` de `MultiserviceBuildBrokerTests` (`Directory not empty`); módulo isolado passou 3/3 e suíte global repetida passou 1008/1008 + 1 skip. `ResourceWarning` de sockets/handles permanece dívida técnica separada.

## Divergências da última reconciliação
### Corrigidas
- Dotfiles Faro foi sincronizado por bundle sem Internet direta; verificador residente repinado para o commit reconciliado.
- LV/ext4 do Faro cresceu online para consumir todo o VG: LV ~198G, filesystem `/` ~195G.
- DNS interno do Faro passou a usar `10.62.91.1`; repositório HTTPS de agent-update voltou a resolver.
- PKI cliente: chave RSA 3072 gerada somente no Faro, CSR assinado pelo Agent PKI, CN/URI=node_id, DNS=faro, cadeia válida.
- Agent 0.36 + updater timer habilitado; heartbeat E2E observado com metadata/telemetria no PostgreSQL.
- R14: `cloudiff-reconcile` gerado e homologado; evidência em `docs/reconciliation/faro-r14-v42.json`.
- Catálogo remoto já contém CloudIFF `0.1.3` em commit concorrente preservado; nenhum commit duplicado foi criado.

### Pendentes de autorização ou capacidade
- Aumentar a VM Faro de 2 para 4 vCPU no hypervisor. Não requer mudança de contrato; após isso rerodar inventário e etapa 6 de aceite.
- Implantar Docker/cAdvisor/monitoramento padrão em unidade própria, desde que os requisitos de capacidade da entrada sejam atendidos.

## Entradas aceitas nesta unidade
- 2 `competencias.yaml`
- 24 `CMakeLists.txt`
- 45 `contratos/nats-security.schema.json`
- 117–122 modelo Faro etapas 1–5
- 125 `contratos/faro-node-preparation.schema.json`
- 126 `config/faro-node-reservation.json`
- 131 `tests/test_faro_node_preparation.py`
- 140 `config/faro-node-profile.json`
- 165 `tests/test_faro_profile.py`
- 179 `skills/cloudiff/SKILL.md` — candidata `0.1.3`
- 182 `tests/test_cloudiff_project_skill.py`
- 1508–1512 reconciliador C++/test/evidência R14

## Entradas ainda pendentes
- 123 `config/faro-validation-06-acceptance.json` — bloqueada por 2/4 vCPU.
- 124 `tests/test_faro_validation_model.py` — consumidor da etapa 6; permanece pendente embora o teste estrutural execute.

## Próxima unidade
- Recarregar `cloudiff@0.1.3`. Se Faro já estiver com 4 vCPU, rerodar inventário/verificador e fechar etapa 6/aceite. Se ainda estiver com 2 vCPU, seguir apenas para entradas independentes que não requeiram o perfil completo, priorizando monitoramento padrão e preparação declarativa, sem Portal e sem mudança de interface.
