# Estado — 2026-08-25 — contrato v43

## Decisões vigentes
- CloudIFF V1/Python e V2/C++23 continuam um único projeto reconciliado incrementalmente.
- `FrozenPortalInterface` permanece requisito mestre: v43 não altera Portal, rotas, navegação ou comportamento visual homologado.
- Skill raiz ativa é `cloudiff@0.1.3`; revisão pós-homologação v43 não encontrou aprendizado novo que exija incremento de versão.
- Faro definitivo é `10.62.91.5`, role `edge`, Ubuntu Server 26.04 x86_64, VM KVM, agent `0.36.0` e heartbeat E2E funcional.
- Monitoramento padrão no Faro usa cAdvisor local em `127.0.0.1:18081`, imagem `ghcr.io/google/cadvisor:v0.57.0` fixada por image ID/digest, sem exposição externa.
- Telemetria continua hierárquica `environment>node>container>service`; agent coleta containers somente via cAdvisor local.
- Requisito prescritivo do Faro permanece 4 vCPU, 8 GiB RAM e 200 GiB disco; ambiente observado tem 2 vCPU e isso não é rebaixado.
- OpenCode/outro agente não é instalado sem autorização explícita.

## Decisões superadas
- Containers/telemetria de container indisponíveis no Faro — superado pela homologação v43 do cAdvisor local.
- Entrada 159 declarada e não gerada — superada pelo instalador idempotente homologado.

## Decisões humanas pendentes
- Nenhuma nova decisão humana.

## Pendências técnicas não humanas
- Faro possui 2 vCPU observadas e requer 4 vCPU; isso mantém pendentes a etapa 6 e o aceite final do node para cargas do perfil completo, incluindo Portal.
- `fwupd-refresh.service` no Faro continua warning externo por timeout de egress LVFS; não afeta CloudIFF interno.
- Cinco arquivos V1 continuam `preexistente` por links Markdown quebrados.
- LegacyRetirement continua bloqueado pela integridade remota do backup principal `pre-v2-20260820` enquanto o servidor de backup estiver fora da rede.
- Acesso direto Hospedagem → `10.68.128.253` continua filtrado; `.253` responde por salto via `10.68.128.252`.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `faro-standard-monitoring-v43`, concluída, sem zona de exclusão ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.3` — skill raiz.
- `desenvolvedor-de-software@14` — método.
- `github-incremental-reconciliation@7` — reconciliação incremental.
- `platform-engineering@ed68466e04c9b5d33898ed5b503fb828f49c3e73` — Docker/runtime/deploy.
- `release-it@1.4.0` — idempotência/rollback/fail-closed.
- `network-ssh-operations@1` — bind loopback e observação de exposição.
- `telemetry-data-visualization@2` — macro global.

## Revisão da skill do projeto
- `cloudiff@0.1.3` revisada após homologação da entrada 159.
- Nenhum aprendizado inesperado novo: digest pinado, idempotência e bind local já pertenciam ao contrato/candidato e passaram sem nova armadilha de projeto.
- Sem incremento artificial de versão.

## Falhas de portão por tipo de entrada
- `deploy`: nenhuma falha funcional. Gate negativo intencional com image ID incorreto retornou código 14 e não alterou o container existente.

## Divergências da última reconciliação
### Corrigidas
- Runtime cAdvisor encontrado antes da retomada foi reconciliado contra o candidato: nome, imagem, image ID, network mode, privilégio, restart policy, mounts e bind casaram exatamente.
- Duas execuções consecutivas do instalador mantiveram o mesmo container ID e `StartedAt`.
- cAdvisor responde `/api/v1.3/machine` e `/api/v1.3/subcontainers` somente em `127.0.0.1:18081`.
- Agent preservou PID e `NRestarts=0`; PostgreSQL observa `telemetry.containers.status=available`, `source=cadvisor-local` e 36 itens no heartbeat validado.

### Pendentes de autorização ou capacidade
- Aumentar a VM Faro de 2 para 4 vCPU no hypervisor; depois rerodar etapa 6/aceite final.

## Entradas aceitas nesta unidade
- 159 `deploy/install_standard_monitoring.sh` — instalador idempotente de cAdvisor local homologado no Faro.

## Entradas ainda pendentes diretamente relevantes
- 123 `config/faro-validation-06-acceptance.json` — bloqueada por 2/4 vCPU.
- 124 `tests/test_faro_validation_model.py` — consumidor da etapa 6.
- 139–163 LegacyRetirement/backup — dependem de integridade remota do backup.

## Próxima unidade
- Se Faro ainda estiver em 2 vCPU, não implantar Portal. Seguir para outra entrada independente e elegível; priorizar preparação declarativa/webdev/observabilidade que não exija perfil completo e não altere a interface congelada.
