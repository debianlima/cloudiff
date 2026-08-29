# Estado — 2026-08-28 — contrato v68

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a correção desta unidade não altera HTML, CSS, JS visual, textos, botões ou layout.
- O link congelado `Visão geral` (`?tab=resumo`) deve produzir o mesmo painel acadêmico canônico servido na raiz do Portal; o renderer administrativo legado não é contrato visual válido para esse alias.
- A promoção produtiva da correção `Visão geral` está homologada: live hash `1ae42e1e...`, `current` no candidato, `previous` no baseline `4407bd7c...`, raiz/alias/navigation equivalentes e verificador residente `errors=0`.
- Faro é o nó CloudIFF de papel `edge`; seu perfil deseja `portal-host`, mas o cutover do Portal ocorre somente após onboarding Faro e portões de portal shadow.
- O onboarding Faro está aceito: 4 vCPU online, identidade própria, PKI/NATS individual, agent não-root, heartbeat direto para Hospedagem, reconciliação/resiliência e rollback já possuem evidência mecânica.
- O heartbeat atual do Faro observa capabilities `inventory`, `health`, `telemetry-host`, `portal-host` e `agent-auto-update`; `build` e `runtime` continuam excluídas do perfil Faro.
- O caminho crítico Faro é `10.62.91.5 -> NATS 10.62.92.7:14222 -> cloudiff-control -> PostgreSQL`; Forja e Maurício não participam do heartbeat crítico.
- Releases de agent-skills permanecem imutáveis; o runtime Faro continua na release instalada `cloudiff@0.1.4`, enquanto a skill de projeto usada nesta unidade é `cloudiff@0.1.24`.

## Decisões superadas
- Salto obrigatório via `172.16.0.1` para acessar máquinas do laboratório — superado em 28/08/2026 pela nova orientação da TI comunicada pelo operador; acesso operacional passa a ser direto pelo conector Labiff, mantendo pfSense/MikroTik apenas como equipamentos de rede quando necessário.
- Faro bloqueado por `2/4 vCPU` — superado em 26/08/2026 após a TI ampliar a VM e o SO observar CPUs `0-3`.
- `portal-host` apenas desejada/não observada — superado pelo heartbeat PostgreSQL atual, que já anuncia `portal-host`; isso não equivale a cutover do Portal.
- Confiar apenas na árvore de uma release de skills já existente como prova do artefato recebido — superado na v45 pelo gate do TAR recebido.

## Decisões humanas pendentes
- Nenhuma decisão humana adicional para aceitar o nó Faro.
- Cutover definitivo do Portal para Faro permanece uma unidade posterior e deve respeitar os portões de portal shadow/FrozenPortalInterface; não foi executado implicitamente nesta unidade.

## Decisões fechadas nesta emenda
- T-016R executou replay real dos dois `project.membership.changed` após autorização humana explícita, criando novos requests e preservando os dead-letters históricos.
- A primeira geração de replay falhou 5/5 e revelou a causa live: `cloudif-forja-agent` lançava `NameError: safe_slug is not defined` em `/project/membership/reconcile`; o worker via `RemoteDisconnected` e persistia apenas `RuntimeError`.
- A correção mínima trocou somente `safe_slug(...)` por `_v118_slug(...)`. No live, foi criada release derivada de `platform-v25-system-fixture-20260821`, sem substituir o arquivo inteiro pelo branch divergente; rollback permanece o pointer anterior.
- Após o fix, Forgejo/Komodo/tenant-access ficaram `ok=true` em ambos os projetos. A segunda geração concluiu `ready` em 1/1 para cada projeto, sem adicionar/remover colaboradores e sem criar terminais.
- Onboarding continua falhando separadamente (`returncode=1`) e permanece T-031; não bloqueia `membership.ok`.

## Pendências técnicas não humanas
- T-031 READY: diagnosticar em leitura o `URLError`/returncode atual do project-onboarding reconcile.
- T-023/T-025 dependem de release C++ nova com manifesto de procedência.
- T-024 segue bloqueada enquanto não existir wiring Gateway→mcp-upload C++.
- O Forja Agent live agora está em release derivada T-016R; consolidar a correção na próxima release normal do runtime sem perder o patch.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `T-016R-membership-deadletters-replay`, concluída; nenhuma zona de exclusão permanece ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.24` — skill raiz; L033 homologado.
- `desenvolvedor-de-software@14` — método PGH.
- `github-incremental-reconciliation@7` — reconciliação incremental.
- `governanca-ontologica-de-skills@1.0.4` — governança.
- `telemetry-data-visualization@2` — macro global; coletor indisponível.

## Falhas de portão por tipo de entrada
- `membership/forja`: helper `safe_slug` inexistente provocava disconnect e falha agregada; corrigido com `_v118_slug`.
- `observabilidade`: worker ainda persiste apenas `error_type` quando a etapa falha; L031/L033 exigem detalhe sanitizado em evolução futura.
- `onboarding`: continua falha separada e não é declarado corrigido por T-016R.

## Divergências da última reconciliação
### Corrigidas
- Entrada 1549 corrige o NameError no endpoint Forja membership.
- Entrada 1550 impede retorno do helper inexistente.
- Entradas 1551/1552 fixam replay, causa live, release derivada, preservação histórica e sucesso final dos dois eventos.
- `cloudiff@0.1.24` registra L033; `VISUAL_DIFF=NO`.

### Pendentes de autorização ou capacidade
- Onboarding atual permanece T-031.
- Próxima release normal do Forja Agent deve absorver o patch da release derivada.

## Entradas aceitas nesta unidade
- 1549 `components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py` — fix `_v118_slug`.
- 1553 `components/runtime/usr/local/sbin/cloudif-forja-agent.py` — mirror runtime byte-idêntico do fix.
- 1550 `tests/test_forja_membership_replay_fix.py`.
- 1551 `docs/reconciliation/membership-deadletters-replay-v68.json`.
- 1552 `tests/test_membership_deadletters_replay_evidence.py`.
- 179 `skills/cloudiff/SKILL.md` — `cloudiff@0.1.24`, L033.
- 2 `competencias.yaml` — skill raiz 0.1.24.
- 9 `estado.md` — snapshot v68.
- 10 `manifesto.yaml` — contrato v68 e zona liberada.

## Próxima unidade
- T-031: diagnosticar onboarding atual em leitura.
- T-024/T-025 somente quando surgirem artefatos de desbloqueio.
