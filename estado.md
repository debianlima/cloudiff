# Estado — 2026-08-22 — contrato v37

## Decisões vigentes
- Core v2: C++23, PostgreSQL, NATS TLS/mTLS, Authentik e migração Strangler; Portal de usuário permanece visualmente imutável.
- Faro: `10.62.91.5`, role `edge`; capabilities iniciais `inventory`, `health`, `telemetry-host`, `portal-host`, `agent-auto-update`; `build`/`runtime` fora do perfil inicial.
- Faro usará Ubuntu Server 26.04 x86_64; recurso solicitado 4 vCPU, 8 GiB e 200 GiB, aguardando confirmação.
- Telemetria canônica usa `environment > node > container > service`, dentro do `node.observed`; `nodes.metadata` no PostgreSQL contém o payload observado atual.
- Agent padrão usa `/opt/cloudiff-agent/releases/<versão>` e symlink atômico `/opt/cloudiff-agent/current`.
- AgentUpdate é pull automático a cada 5 min + jitter, manifesto assinado Ed25519, SHA-256/tamanho, rollback automático se serviço falhar. Agent permanece não-root; updater é helper root separado.
- Repositório AgentUpdate fica em Hospedagem apenas `127.0.0.1:18250`, Nginx read-only; nodes acessam por `https://cloudiff.duckdns.org/__cloudiff_agent_updates` via NPM Maurício → router Hospedagem → loopback.
- SSH permanece apenas bootstrap/emergência; atualização normal não depende de SSH.
- Reboot de recovery é permitido por padrão, com futura opção `/admin` por node para desativá-lo.
- Recuperação de Faro pode ser reinstalação total; nenhum backup de host é requisito.
- Backup principal candidato preservado: conjunto remoto `pre-v2-20260820`; destruição de legado continua bloqueada até os três snapshots passarem integridade e todo runtime dependente estar substituído.

## Decisões superadas
- Agent em `/opt/cloudiff-v2/current/bin/cloudiff-agent` — substituído pelo layout padrão `/opt/cloudiff-agent/current`.
- Atualização permanente por SSH — substituída por AgentUpdate assinado e automático.
- Repositório direto `10.62.92.7:18250` para nodes — reprovado por conectividade inter-VLAN e substituído em v33 pelo HTTPS NPM/router; entradas pendentes 166-168 foram retiradas da emenda e seus artefatos removidos.
- Faro role/capabilities unresolved — substituído por edge + portal/telemetry/update.

## Pendências abertas
- Faro ainda sem SSH/onboarding real/PKI/reboot E2E.
- Confirmação do recurso Faro 4 vCPU/8 GiB/200 GiB.
- AdminObservability `/admin`: 138, 151-159 pendentes.
- LegacyRetirement: 139, 160-163 pendentes; snapshot Maurício `pre-v2` ainda incompleto na verificação local/remota temporariamente indisponível.
- Portal ainda reside em Hospedagem e depende de serviços Python legados; migração para Faro só depois do onboarding e de shadow/cutover próprios.

## Revisão de competências v33
- `rede`, `plataforma`, `dist`, `resiliencia` e `release` continuaram adequadas após a troca porta direta → HTTPS. Nenhuma competência nova ou substituição.

## Revisão de competências v34
- AdminObservability: `dist` cobre desired/observed e policy pull; `cpp` cobre backend no agent binary; `plataforma` cobre serviço; `ui-compat` cobre `/admin`; `resiliencia` cobre reboot/rollback. Nenhuma competência nova ou troca.

## Revisão de competências v35
- `rede`, `plataforma`, `dist`, `resiliencia` e `release` continuam adequadas para policy pull do AgentUpdate. Nenhuma competência nova ou substituição.

## Revisão de competências v36
- `dist` cobre reconnect, partição e falha injetada; `plataforma`/`resiliencia` cobrem readiness e boot recovery. `rede` permanece relevante para o caminho NATS. Nenhuma competência nova ou substituição necessária.

## Revisão de competências v37
- `plataforma`, `navegacao`/Playwright e `cloudiff-ephemeral-workspace` cobrem o WebDevWorkspace; sincronização de skills é operação de plataforma. Nenhum OpenCode/agente adicional autorizado ou necessário.

## Competências ativas
cpp, dist, plataforma, ui-compat — próxima unidade AdminObservability/monitoramento padrão

## Falhas de portão por tipo de entrada
- build-cpp: primeiro CTest v32 sem `CLOUDIFF_POSTGRES_CONNINFO`; corrigido pela pré-condição existente e passou 12/12 Debug e 12/12 Release.
- rede: acesso direto Forja→Hospedagem:18250 bloqueado antes do host; v33 migrou para HTTPS existente sem abrir porta inter-VLAN.
- deploy: repository Nginx inicialmente tentou `/var/cache/nginx/client_temp` em rootfs read-only; corrigido para `/tmp` e entrypoint direto, mantendo hardening.
- verificação: primeira consulta de telemetria usou coluna inexistente `nodes.observed_state`; coluna real é `nodes.metadata`; telemetria foi comprovada nela.
- backup: snapshot Maurício pre-v2 ainda não validado integralmente; destruição permanece bloqueada.

## Entradas aceitas
- Base histórica aceita preservada.
- Telemetria/perfil Faro v32: 1,3,15,24,31,32,125,126,136,140-143 aceitos.
- AgentUpdate v33: 36,137,144-150,164,169-170 aceitos.

## Entradas pendentes
20, 26, 138-139, 151-163, 165

## Evidência de portão — AgentUpdate
- Agent v32 Debug e Release: Clang, 0 warnings, CTest 12/12 em ambos; jobs PostgreSQL=0 e worker restaurado.
- Manifesto de release 0.32.0 assinado Ed25519; assinatura, SHA-256 e tamanho validados.
- Chave de assinatura: root-only em Hospedagem; repositório contém apenas artefatos públicos assinados.
- Repository: Nginx read-only, cap-drop ALL, no-new-privileges, backend somente 127.0.0.1:18250, NRestarts=0 após correção.
- HTTPS route: Forja GET 200; POST 403; query 400; porta direta 18250 bloqueada; rollback gera 404 e reapply restaura 200.
- Forja foi migrada primeiro de 0.7.0 para layout padrão sem mudança funcional; depois AgentUpdate aplicou 0.32.0 assinado.
- Forja: assinatura inválida bloqueada sem trocar current; segunda checagem NOOP; rollback para 0.7.0 passou; reapply 0.32.0 passou; timer ativo/enabled.
- PostgreSQL `nodes.metadata`: Forja reporta hierarchy completa, agent_version 0.32.0 e containers.status=available.

## Próxima unidade
AdminObservability v34: backend loopback sobre PostgreSQL, `/admin` somente CloudIF-Tenants-Admin, NodeRecoveryPolicy em desired_state e pull HTTPS pelo updater; depois monitoring padrão 159 e perfil Faro 165.
