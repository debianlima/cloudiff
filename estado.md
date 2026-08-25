# Estado — 2026-08-24 — contrato v41

## Decisões vigentes
- CloudIFF V1/Python e V2/C++23 permanecem um único projeto; reconciliação incremental antecede normalização, migração ou remoção.
- `FrozenPortalInterface` continua sendo o requisito mestre: implementação pode mudar; interface gráfica, navegação, rotas e comportamento visível homologado não mudam sem decisão humana explícita separada.
- Skill raiz ativa é `cloudiff@0.1.2`; revisão de cobertura da v41 concluída sem nova versão porque L009 já define o gate homologado de reconexão por heartbeat sem restart.
- Agentes centrais usam release imutável `0.36.0` via updater assinado Ed25519. Forja, Maurício e Hospedagem estão com timer de auto-update `enabled` e `active`.
- O control-plane usa unit com `ExecStartPre` baseado em `pg_isready`; indisponibilidade temporária do PostgreSQL deixa o serviço em `activating/start-pre`, não em StartLimit/falha.
- Faro continua alvo efetivo quando a unidade elegível exigir deploy real; nenhuma mudança de interface será acoplada ao onboarding.
- OpenCode ou outro agente auxiliar não é instalado em servidor/container sem autorização explícita.

## Decisões superadas
- Agentes `0.34.0` como baseline operacional — substituídos por `0.36.0` após build, CTest, canary e outage real.
- Considerar `systemctl active` como evidência suficiente de saúde do agente — superado: gate exige PID preservado + heartbeat/`last_seen` retomado após outage.
- Unit do control sem espera ativa por PostgreSQL — substituída pela unit canônica com `ExecStartPre=/usr/bin/timeout 120 ... pg_isready`.
- Timer de updater da Hospedagem desabilitado durante a recuperação — reativado após v41, retornando `AGENT_UPDATE=NOOP` em 0.36.0.

## Decisões humanas pendentes
- Nenhuma decisão humana nova bloqueia o fecho v41.

## Pendências técnicas não humanas
- Cinco arquivos V1 continuam `preexistente` porque a auditoria integral encontrou links Markdown quebrados; não foram alterados nesta unidade.
- Sete entradas declaradas continuam não geradas: LegacyRetirement, monitoramento padrão e teste de perfil Faro.
- Backup principal `pre-v2-20260820` continua sem integridade remota completa enquanto o servidor de backup estiver fora da rede; remoção destrutiva de legacy segue bloqueada.
- A suíte Python oficial ainda pode emitir `ResourceWarning` de handles/sockets no teardown; dívida independente da v41.
- Acesso direto Hospedagem (`10.62.92.7`) → `10.68.128.253` segue filtrado; `.253` responde ICMP e SSH pela rede local através de `10.68.128.252`. SSH `cti` no `.253` foi comprovado via salto.

## Trabalho compartilhado
- `manifesto.yaml.trabalho_compartilhado` — unidade `reconnect-readiness-v41`, concluída, sem zona de exclusão ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.2` — skill raiz do projeto.
- `desenvolvedor-de-software@14` — método de projeto.
- `github-incremental-reconciliation@7` — reconciliação/delta antes de normalizar.
- `cloud-design-patterns` no commit fixado — reconnect/falha injetada.
- `platform-engineering` no commit fixado — readiness/systemd/runtime.
- `release-it@1.4.0` — promoção assinada/canary/rollback.
- `distributed-agent-control@1` — agentes, heartbeat e reconexão.
- `network-ssh-operations@1` — caminho NATS e testes de conectividade.
- `telemetry-data-visualization@2` — macro global de telemetria da unidade.

## Revisão da skill do projeto
- Cobertura revisada após homologação v41.
- Nenhuma nova entrada foi adicionada à skill porque L009 já contém exatamente o aprendizado homologado: agente `active` não prova reconexão; o gate é retomada de `last_seen`/heartbeat sem restart do agente.
- `cloudiff@0.1.2` permanece a versão ativa; não houve incremento artificial de versão.

## Portões v41
- Build Debug 0.36: 63/63 targets, Clang, ASan/UBSan, zero warnings.
- Build Release 0.36: 63/63 targets, zero warnings.
- CTest Debug: 13/13 PASS com worker parado.
- CTest Release: 13/13 PASS com worker parado.
- Teste NATS isolado: primeiro publish/subscription PASS; marcador `NATS_RECONNECT_READY`; NATS temporário reiniciado; segunda publicação recebida sem restart do processo.
- Publicação 0.36: Ed25519 signature PASS, SHA-256/size PASS; chave privada `0600 root:root`.
- Canary Forja: updater `APPLIED VERSION=0.36.0`, agente ativo, heartbeat fresco.
- Maurício: já havia aplicado 0.36 automaticamente; updater manual retornou `NOOP`.
- Hospedagem: updater `APPLIED VERSION=0.36.0`, agente ativo.
- Outage NATS real: container NATS reiniciado por ~1s; Forja, Maurício e Hospedagem mantiveram os mesmos PIDs, `NRestarts=0` e avançaram `last_seen` em 60–75s.
- Readiness control/PostgreSQL: com DB parado, control ficou `activating/start-pre`; após DB voltar, control ficou `active`, `NRestarts=0`; worker foi restaurado `active`.
- Auto-update: timers dos três nós `enabled+active`, checks finais `AGENT_UPDATE=NOOP`.
- Interface: nenhum arquivo de UI/FrozenPortalInterface foi alterado nesta unidade.

## Divergências corrigidas
- Fonte canônica já continha o reparo 0.36, mas runtime ainda usava agent 0.34 e unit antiga do control; v41 promoveu/homologou o estado canônico.
- Forja e Maurício estavam `active` mas com `Connection Closed`; v41 provou reconexão funcional por heartbeat após outage real.
- Hospedagem estava com updater timer desabilitado desde recuperação anterior; v41 restaurou a política de auto-update contínuo.

## Entradas aceitas nesta unidade
- 27 `include/cloudiff/nats_client.hpp` — interface do cliente NATS homologada com reconexão.
- 28 `src/common/nats_client.cpp` — reconnect automático homologado em outage isolado e real.
- 33 `tests/test_nats_client.cpp` — marcador determinístico `NATS_RECONNECT_READY` e gate de segunda publicação.
- 37 `deploy/systemd/cloudiff-v2-control.service` — readiness PostgreSQL homologado em indisponibilidade real.
- 142 `src/common/telemetry.cpp` — versão 0.36 observada no fluxo de heartbeat.

## Estado operacional relevante
- Hospedagem: `/` ~195 GiB, ~150 GiB livres após expansão de disco/LVM/ext4; PostgreSQL, control, worker, agent e NATS ativos.
- Forja/Maurício/Hospedagem: agent `0.36.0`, updater timer habilitado e ativo.
- `10.68.128.253` (`vmnova`) está vivo e acessível via `10.68.128.252`; acesso direto da Hospedagem é filtrado entre redes.

## Próxima unidade
- Reconciliar o perfil/máquina Faro real (`10.62.91.5`) contra inventário PGH e recursos observados; depois implantar nele os serviços Faro elegíveis, começando por agent/telemetria/update e somente então Portal, sempre preservando a interface existente.
