# Estado — 2026-08-25 — contrato v44

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre: a v44 não altera Portal/UI, navegação, rotas de usuário ou comportamento visual homologado.
- WebDevWorkspace fica em Forja como navegador Selenium/noVNC isolado, sem Docker socket, sem privilégio, sem OpenCode/agente adicional e com `/workspace` read-only.
- Link operacional fixo: `https://cloudiff.duckdns.org/__cloudiff_webdev/`, restrito à VPN `10.0.0.0/16`; NPM em Maurício é a única origem proxy permitida no backend Forja.
- Acesso direto `http://10.62.91.2:17900/` permanece apenas para origens explicitamente permitidas pelo firewall do WebDev; Faro e Hospedagem não têm bypass direto.
- Simulações/read-only de infraestrutura no WebDev usam DNS/AD físico `10.68.128.252`; não há agente adicional dentro do container.
- Skill ativa durante a unidade foi `cloudiff@0.1.3`. A homologação produziu `cloudiff@0.1.4` com L013; a nova versão só ativa na próxima unidade.
- Catálogo PGH registra `cloudiff@0.1.4` em `2a641bfe597377a55711ea0804c602ea999fda07`.

## Decisões superadas
- `apply` do WebDev sempre reiniciar `cloudiff-webdev.service` — superado: runtime equivalente executa firewall/health e retorna `WEBDEV_WORKSPACE=NOOP`, preservando sessão/container.
- Link operacional principal apenas `http://10.62.91.2:17900/` — superado pelo HTTPS fixo VPN-only; o link direto permanece apenas como canal interno restrito.

## Decisões humanas pendentes
- Nenhuma nova decisão humana na v44.

## Pendências técnicas não humanas
- Faro continua com 2 vCPU observadas para requisito prescritivo de 4 vCPU; Portal não deve migrar para Faro até o recurso ser corrigido e a etapa 6 ser rerodada.
- Faro possui egress Internet filtrado: CloudIFF interno/NATS/heartbeat funcionam, mas GitHub/LVFS externos expiram. `fwupd-refresh.service` permanece warning de máquina por timeout LVFS.
- Cinco arquivos V1 continuam `preexistente` por links Markdown quebrados.
- LegacyRetirement continua bloqueado pela integridade remota do backup principal `pre-v2-20260820` enquanto o servidor de backup estiver indisponível.
- Acesso direto Hospedagem → `10.68.128.253` permanece filtrado; `.253` responde via salto por `10.68.128.252`.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `webdev-workspace-v44`, concluída, sem zona de exclusão ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.3` — skill raiz usada durante a execução.
- `desenvolvedor-de-software@14` — método PGH.
- `github-incremental-reconciliation@7` — reconciliação antes de normalização/release.
- `governanca-ontologica-de-skills@1.0.4` — atualização da skill e catálogo após homologação.
- `platform-engineering@ed68466e04c9b5d33898ed5b503fb828f49c3e73` — Docker/systemd/runtime.
- `release-it@1.4.0` — idempotência e rollback.
- `network-ssh-operations@1` — allowlists, NPM, WebSocket e bypass negativo.
- `operational-ui-truth@1` — navegador real/efeito observado sem alterar UI.
- `telemetry-data-visualization@2` — macro global da unidade.

## Competências instaladas/atualizadas para unidades futuras
- `cloudiff@0.1.4` — L013: apply idempotente preserva container ID/StartedAt e evita restart de runtime equivalente.

## Falhas de portão por tipo de entrada
- `deploy` entrada 174: primeira prova de idempotência reprovou porque duas execuções consecutivas recriavam o container; corrigido com `runtime_equivalent` + `WEBDEV_WORKSPACE=NOOP`.
- `runtime` candidata v44: release antiga tinha unit em `deploy/cloudiff-webdev.service`, enquanto o instalador self-relative espera `deploy/systemd/cloudiff-webdev.service`; layout da candidata foi reconciliado antes do gate final.
- `higiene`: scanner inicial tratou `SE_VNC_NO_PASSWORD: "true"` como segredo; gate foi corrigido para distinguir marcador booleano `NO_PASSWORD` de atribuição de senha real, sem alterar o teste correto.
- `automacao`: primeira recriação de sessão WebDriver após restart encontrou slot transitório; sessão dedicada foi reconciliada e o gate final de navegação passou.

## Divergências da última reconciliação
### Corrigidas
- Catálogo remoto avançou de `998b625...` até `2a641bf...`; as sete referências internas do CloudIFF foram comparadas e permaneceram byte a byte inalteradas antes do checkpoint avançar.
- WebDev runtime passou a apontar novamente para `/var/lib/cloudiff-webdev/v44`, não para worktree de desenvolvimento.
- Instalador WebDev agora é idempotente: duas aplicações consecutivas preservaram exatamente o mesmo container ID e `StartedAt`.
- Rota NPM passou rollback→reapply e retornou ao mesmo SHA de configuração.
- WebSocket real pelo HTTPS fixo respondeu `101 Switching Protocols`.
- Selenium navegou o Portal real e foi redirecionado corretamente ao Authentik; sessão visível ficou aberta no noVNC.

### Pendentes de autorização ou capacidade
- Liberar/ajustar 4 vCPU no hypervisor do Faro.
- Egress externo do Faro exige correção no gateway/ACL; nenhum canal administrativo do gateway estava exposto pelos endereços/portas testados.

## Entradas aceitas nesta unidade
- 2 `competencias.yaml` — skill projeto candidata 0.1.4 e checkpoints reconciliados.
- 171 `contratos/webdev-workspace.schema.json` — contrato WebDev v2.
- 172 `config/webdev-workspace.json` — link HTTPS fixo e política VPN-only.
- 173 `deploy/compose.webdev.yaml` — Selenium isolado, imagem pinada e mounts restritos.
- 174 `deploy/install_webdev_workspace.sh` — apply idempotente homologado.
- 175 `tests/test_webdev_workspace.py` — gates de isolamento, configuração e idempotência.
- 178 `deploy/systemd/cloudiff-webdev.service` — runtime systemd homologado.
- 179 `skills/cloudiff/SKILL.md` — candidata `cloudiff@0.1.4` com L013.
- 182 `tests/test_cloudiff_project_skill.py` — versão/ontologia/anti-ciclo atualizados.
- 1513 `deploy/install_webdev_route.sh` — rota NPM HTTPS reversível.
- 1514 `tests/test_webdev_route.py` — VPN-only, websocket, rollback e ausência de bypass.

## Portões v44
- `WEBDEV_WORKSPACE_OFFLINE=PASS`.
- `WEBDEV_ROUTE_OFFLINE=PASS`.
- WebDev runtime: container healthy, imagem digest pinada, `privileged=false`, Docker socket ausente, workspace read-only.
- Idempotência: duas aplicações consecutivas `NOOP`, container ID e `StartedAt` inalterados.
- NPM: `nginx -t` PASS; rollback removeu bloco; reapply restaurou SHA original.
- Acesso fixo: Forja/Hospedagem 200; Faro 403.
- Bypass direto: Faro/Hospedagem bloqueados.
- WebSocket HTTPS: `101 Switching Protocols`.
- Selenium: navegação real PASS; Authentik observado no navegador visível.
- Frozen UI: 6/6 PASS; nenhum arquivo Portal/UI no diff.
- Suíte oficial: 1008 testes PASS + 1 skip.
- Namespace: zero extras e zero ausências obrigatórias; cinco pendências LegacyRetirement continuam declaradas e não geradas.
- Secret scan e `git diff --check`: PASS.
- Catálogo: `CATALOGO_SKILLS=PASS`, `SYNC_GUARD=PASS`.

## Próxima unidade
- Recarregar `cloudiff@0.1.4` antes de qualquer nova unidade.
- Enquanto Faro permanecer 2/4 vCPU, não migrar Portal. Priorizar pendência independente que não altere a interface: reconciliar egress externo do Faro se surgir canal administrativo seguro do gateway; caso contrário seguir outra entrada elegível fora de LegacyRetirement/Portal.
