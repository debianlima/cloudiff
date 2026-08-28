# Estado — 2026-08-28 — contrato v66

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a correção desta unidade não altera HTML, CSS, JS visual, textos, botões ou layout.
- O link congelado `Visão geral` (`?tab=resumo`) deve produzir o mesmo painel acadêmico canônico servido na raiz do Portal; o renderer administrativo legado não é contrato visual válido para esse alias.
- A promoção produtiva da correção `Visão geral` está homologada: live hash `1ae42e1e...`, `current` no candidato, `previous` no baseline `4407bd7c...`, raiz/alias/navigation equivalentes e verificador residente `errors=0`.
- Faro é o nó CloudIFF de papel `edge`; seu perfil deseja `portal-host`, mas o cutover do Portal ocorre somente após onboarding Faro e portões de portal shadow.
- O onboarding Faro está aceito: 4 vCPU online, identidade própria, PKI/NATS individual, agent não-root, heartbeat direto para Hospedagem, reconciliação/resiliência e rollback já possuem evidência mecânica.
- O heartbeat atual do Faro observa capabilities `inventory`, `health`, `telemetry-host`, `portal-host` e `agent-auto-update`; `build` e `runtime` continuam excluídas do perfil Faro.
- O caminho crítico Faro é `10.62.91.5 -> NATS 10.62.92.7:14222 -> cloudiff-control -> PostgreSQL`; Forja e Maurício não participam do heartbeat crítico.
- Releases de agent-skills permanecem imutáveis; o runtime Faro continua na release instalada `cloudiff@0.1.4`, enquanto a skill de projeto usada nesta unidade é `cloudiff@0.1.22`.

## Decisões superadas
- Salto obrigatório via `172.16.0.1` para acessar máquinas do laboratório — superado em 28/08/2026 pela nova orientação da TI comunicada pelo operador; acesso operacional passa a ser direto pelo conector Labiff, mantendo pfSense/MikroTik apenas como equipamentos de rede quando necessário.
- Faro bloqueado por `2/4 vCPU` — superado em 26/08/2026 após a TI ampliar a VM e o SO observar CPUs `0-3`.
- `portal-host` apenas desejada/não observada — superado pelo heartbeat PostgreSQL atual, que já anuncia `portal-host`; isso não equivale a cutover do Portal.
- Confiar apenas na árvore de uma release de skills já existente como prova do artefato recebido — superado na v45 pelo gate do TAR recebido.

## Decisões humanas pendentes
- Nenhuma decisão humana adicional para aceitar o nó Faro.
- Cutover definitivo do Portal para Faro permanece uma unidade posterior e deve respeitar os portões de portal shadow/FrozenPortalInterface; não foi executado implicitamente nesta unidade.

## Decisões fechadas nesta emenda
- T-016 auditou em leitura os dois `project.membership.changed` históricos; nenhuma fila foi replayada e nenhum efeito externo foi solicitado.
- A causa exata histórica permanece `NAO DECLARADA`: o dead-letter persiste apenas `RuntimeError/error_type` e os journals antigos não preservam o request detail.
- O estado atual está convergido para ambos os projetos: owner/ACL central, tenant access, repositório Forgejo sem colaboradores extras e terminal do owner no Komodo. Não há item não-terminal atual para esses projetos.
- Replay não é tecnicamente necessário sob o estado observado e continua bloqueado por efeitos + autorização humana separada.
- O `project-onboarding-reconcile` atualmente falha com `URLError` para ambos os projetos; isso é T-031 separado, pois onboarding não participa do booleano `membership.ok`.

## Pendências técnicas não humanas
- T-031 READY: diagnosticar em leitura o `URLError` atual do `cloudif-project-onboarding-reconcile.service` para os dois projetos.
- T-021 segue READY para completar o gate live de admin-observability.
- T-023/T-025 dependem de release C++ nova com manifesto de procedência.
- T-024 segue bloqueada enquanto não existir wiring Gateway→mcp-upload C++.
- T-016R permanece bloqueada: estado atual convergido e replay não justificado.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `T-016-membership-deadletters-readonly`, concluída; nenhuma zona de exclusão permanece ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.22` — skill raiz; L031 homologado.
- `desenvolvedor-de-software@14` — método PGH.
- `github-incremental-reconciliation@7` — reconciliação incremental.
- `governanca-ontologica-de-skills@1.0.4` — governança.
- `telemetry-data-visualization@2` — macro global; coletor indisponível.

## Falhas de portão por tipo de entrada
- `observabilidade`: dead-letter guarda somente `error_type`; causa histórica exata não pode ser reconstruída após expiração dos journals.
- `onboarding`: reconcile atual retorna `URLError` para ambos os projetos; separado em T-031.

## Divergências da última reconciliação
### Corrigidas
- Entrada 1545 fixa a diferença entre causa histórica não provada e convergência atual observada.
- Entrada 1546 impede overclaim de causa/replay e garante que onboarding atual não seja confundido com a falha membership histórica.
- `cloudiff@0.1.22` registra L031; `VISUAL_DIFF=NO`.

### Pendentes de autorização ou capacidade
- Replay T-016R continua bloqueado e sem necessidade técnica observada.
- T-031 pode ser executado read-only sem replay.

## Entradas aceitas nesta unidade
- 1545 `docs/reconciliation/membership-deadletters-readonly-v66.json`.
- 1546 `tests/test_membership_deadletters_readonly_evidence.py`.
- 179 `skills/cloudiff/SKILL.md` — `cloudiff@0.1.22`, L031.
- 2 `competencias.yaml` — skill raiz 0.1.22.
- 9 `estado.md` — snapshot v66.
- 10 `manifesto.yaml` — contrato v66 e zona liberada.

## Próxima unidade
- T-021: completar gate live de `admin-observability` C++.
- T-031: diagnosticar onboarding atual em leitura.
