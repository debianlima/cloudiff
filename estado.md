# Estado — 2026-08-28 — contrato v69

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a correção desta unidade não altera HTML, CSS, JS visual, textos, botões ou layout.
- O link congelado `Visão geral` (`?tab=resumo`) deve produzir o mesmo painel acadêmico canônico servido na raiz do Portal; o renderer administrativo legado não é contrato visual válido para esse alias.
- A promoção produtiva da correção `Visão geral` está homologada: live hash `1ae42e1e...`, `current` no candidato, `previous` no baseline `4407bd7c...`, raiz/alias/navigation equivalentes e verificador residente `errors=0`.
- Faro é o nó CloudIFF de papel `edge`; seu perfil deseja `portal-host`, mas o cutover do Portal ocorre somente após onboarding Faro e portões de portal shadow.
- O onboarding Faro está aceito: 4 vCPU online, identidade própria, PKI/NATS individual, agent não-root, heartbeat direto para Hospedagem, reconciliação/resiliência e rollback já possuem evidência mecânica.
- O heartbeat atual do Faro observa capabilities `inventory`, `health`, `telemetry-host`, `portal-host` e `agent-auto-update`; `build` e `runtime` continuam excluídas do perfil Faro.
- O caminho crítico Faro é `10.62.91.5 -> NATS 10.62.92.7:14222 -> cloudiff-control -> PostgreSQL`; Forja e Maurício não participam do heartbeat crítico.
- Releases de agent-skills permanecem imutáveis; o runtime Faro continua na release instalada `cloudiff@0.1.4`, enquanto a skill de projeto usada nesta unidade é `cloudiff@0.1.25`.

## Decisões superadas
- Salto obrigatório via `172.16.0.1` para acessar máquinas do laboratório — superado em 28/08/2026 pela nova orientação da TI comunicada pelo operador; acesso operacional passa a ser direto pelo conector Labiff, mantendo pfSense/MikroTik apenas como equipamentos de rede quando necessário.
- Faro bloqueado por `2/4 vCPU` — superado em 26/08/2026 após a TI ampliar a VM e o SO observar CPUs `0-3`.
- `portal-host` apenas desejada/não observada — superado pelo heartbeat PostgreSQL atual, que já anuncia `portal-host`; isso não equivale a cutover do Portal.
- Confiar apenas na árvore de uma release de skills já existente como prova do artefato recebido — superado na v45 pelo gate do TAR recebido.

## Decisões humanas pendentes
- Nenhuma decisão humana adicional para aceitar o nó Faro.
- Cutover definitivo do Portal para Faro permanece uma unidade posterior e deve respeitar os portões de portal shadow/FrozenPortalInterface; não foi executado implicitamente nesta unidade.

## Decisões fechadas nesta emenda
- T-031 provou a causa da falha atual de onboarding sem executar reconcile manual nem alterar runtime: o `cloudif-supabase-release-agent.service` falhava em `226/NAMESPACE` porque `/srv/cloudif/managed-backups/releases`, declarado em `ReadWritePaths`, não existia.
- No último ciclo falho, Forja e Komodo responderam HTTP 200; a falha ocorreu depois, no acesso ao Supabase Release Agent.
- Trabalho concorrente criou/restaurou o path `0700 root:root` e reiniciou o Release Agent às 01:04:37 UTC. O inspect Supabase voltou a 200 às 01:04:49/51 e o onboarding passou 2/2 às 01:04:51, mantendo `ready=2` nos ciclos seguintes.
- A correção live não é atribuída a T-031; esta unidade foi read-only. O ator exato além de `cti via sudo` permanece `NAO DECLARADO`.
- A causa T-031 não reclassifica automaticamente os dead-letters históricos de 05/08 e 07/08.

## Pendências técnicas não humanas
- T-034 READY: analisar consumidores/runtime UID-GID de `/srv/cloudif/proxy/npm/data/keys.json` antes de qualquer hardening de permissão.
- T-028 READY: investigar em leitura o gatilho externo do reboot pfSense no hypervisor; não tocar no pfSense.
- T-033 READY: melhorar observabilidade do reconcile worker para persistir etapa/upstream/erro sanitizado.
- T-035 READY: tratar warning de sintaxe HTTP/2 NPM em unidade separada.
- T-023/T-025/T-032 permanecem dependentes de releases futuras; T-024 depende de wiring explícito.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `T-031-project-onboarding-diagnostico`, concluída; nenhuma zona de exclusão permanece ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.25` — skill raiz; L034 homologado.
- `desenvolvedor-de-software@14` — método PGH.
- `github-incremental-reconciliation@7` — reconciliação incremental.
- `governanca-ontologica-de-skills@1.0.4` — governança.
- `telemetry-data-visualization@2` — macro global; coletor indisponível.

## Falhas de portão por tipo de entrada
- `systemd-sandbox`: `ReadWritePaths` apontava para diretório ausente; unit falhava antes do ExecStart com 226/NAMESPACE.
- `observabilidade`: consumer reportava apenas `URLError`, exigindo correlação com journal do upstream para localizar o namespace failure.

## Divergências da última reconciliação
### Corrigidas
- Entrada 1554 fixa a cadeia causal e separa a recuperação concorrente da ação desta unidade.
- Entrada 1555 exige evidência de 226/NAMESPACE, path ausente, inspect 200 pós-recuperação e onboarding 2/2.
- `cloudiff@0.1.25` registra L034; `VISUAL_DIFF=NO`.

### Pendentes de autorização ou capacidade
- Nenhuma mutação adicional no onboarding é necessária enquanto health/ready permanecerem verdes.
- Hardening NPM T-034 exige análise de consumidores e decisão humana antes de chmod/chown.

## Entradas aceitas nesta unidade
- 1554 `docs/reconciliation/project-onboarding-urllerror-v69.json`.
- 1555 `tests/test_project_onboarding_urllerror_evidence.py`.
- 179 `skills/cloudiff/SKILL.md` — `cloudiff@0.1.25`, L034.
- 2 `competencias.yaml` — skill raiz 0.1.25.
- 9 `estado.md` — snapshot v69.
- 10 `manifesto.yaml` — contrato v69 e zona liberada.

## Próxima unidade
- T-034: análise read-only do `NPM data/keys.json` e seus consumidores antes de decisão de hardening.
- T-028: diagnóstico read-only do hypervisor, sem tocar no pfSense.
