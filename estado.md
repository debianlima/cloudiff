# Estado — 2026-08-28 — contrato v67

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a correção desta unidade não altera HTML, CSS, JS visual, textos, botões ou layout.
- O link congelado `Visão geral` (`?tab=resumo`) deve produzir o mesmo painel acadêmico canônico servido na raiz do Portal; o renderer administrativo legado não é contrato visual válido para esse alias.
- A promoção produtiva da correção `Visão geral` está homologada: live hash `1ae42e1e...`, `current` no candidato, `previous` no baseline `4407bd7c...`, raiz/alias/navigation equivalentes e verificador residente `errors=0`.
- Faro é o nó CloudIFF de papel `edge`; seu perfil deseja `portal-host`, mas o cutover do Portal ocorre somente após onboarding Faro e portões de portal shadow.
- O onboarding Faro está aceito: 4 vCPU online, identidade própria, PKI/NATS individual, agent não-root, heartbeat direto para Hospedagem, reconciliação/resiliência e rollback já possuem evidência mecânica.
- O heartbeat atual do Faro observa capabilities `inventory`, `health`, `telemetry-host`, `portal-host` e `agent-auto-update`; `build` e `runtime` continuam excluídas do perfil Faro.
- O caminho crítico Faro é `10.62.91.5 -> NATS 10.62.92.7:14222 -> cloudiff-control -> PostgreSQL`; Forja e Maurício não participam do heartbeat crítico.
- Releases de agent-skills permanecem imutáveis; o runtime Faro continua na release instalada `cloudiff@0.1.4`, enquanto a skill de projeto usada nesta unidade é `cloudiff@0.1.23`.

## Decisões superadas
- Salto obrigatório via `172.16.0.1` para acessar máquinas do laboratório — superado em 28/08/2026 pela nova orientação da TI comunicada pelo operador; acesso operacional passa a ser direto pelo conector Labiff, mantendo pfSense/MikroTik apenas como equipamentos de rede quando necessário.
- Faro bloqueado por `2/4 vCPU` — superado em 26/08/2026 após a TI ampliar a VM e o SO observar CPUs `0-3`.
- `portal-host` apenas desejada/não observada — superado pelo heartbeat PostgreSQL atual, que já anuncia `portal-host`; isso não equivale a cutover do Portal.
- Confiar apenas na árvore de uma release de skills já existente como prova do artefato recebido — superado na v45 pelo gate do TAR recebido.

## Decisões humanas pendentes
- Nenhuma decisão humana adicional para aceitar o nó Faro.
- Cutover definitivo do Portal para Faro permanece uma unidade posterior e deve respeitar os portões de portal shadow/FrozenPortalInterface; não foi executado implicitamente nesta unidade.

## Decisões fechadas nesta emenda
- T-021 completou a prova live read-only do `AdminObservability` C++ em `127.0.0.1:18260`, versão `0.34.0-shadow`, consumido pelo Portal live.
- Auth foi provada: backend sem token 401, Portal sem grupo admin 403 e Portal com `CloudIF-Tenants-Admin` 200 para environment/policy.
- Os GETs foram observacionalmente sem efeito: `desired_state` e `audit_log` de recovery ficaram byte-logicamente equivalentes por contadores/revisions antes/depois; nenhum POST recovery foi executado.
- Autoridade C++ aceita somente no escopo read-only observacional. O efeito de recovery não foi homologado nem inferido.
- Procedência 0.34 permanece `NAO DECLARADO`: release sem manifest, versão ausente do histórico remoto C++ e branch atual em 0.36.

## Pendências técnicas não humanas
- T-031 READY: diagnosticar em leitura o `URLError` atual do project-onboarding reconcile.
- T-023/T-025 dependem de release C++ nova com manifesto de procedência.
- T-024 segue bloqueada enquanto não existir wiring Gateway→mcp-upload C++.
- Recovery write do AdminObservability não foi exercido em T-021 e não é declarado como paridade de efeito.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `T-021-admin-observability-live`, concluída; nenhuma zona de exclusão permanece ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.23` — skill raiz; L032 homologado.
- `desenvolvedor-de-software@14` — método PGH.
- `github-incremental-reconciliation@7` — reconciliação incremental.
- `governanca-ontologica-de-skills@1.0.4` — governança.
- `telemetry-data-visualization@2` — macro global; coletor indisponível.

## Falhas de portão por tipo de entrada
- `proveniencia`: binário live AdminObservability 0.34 sem release manifest/commit-fonte comprovado.
- `efeito`: POST recovery não faz parte do gate read-only e permanece não homologado nesta unidade.

## Divergências da última reconciliação
### Corrigidas
- T-021 deixou de estar bloqueada por rede: Portal live consome o C++ e os GETs preservam estado persistente.
- Entradas 1541/1542 ficam aceitas como evidência histórica verdadeira do bloqueio v64; 1547/1548 registram o gate live v67.
- `cloudiff@0.1.23` registra L032; `VISUAL_DIFF=NO`.

### Pendentes de autorização ou capacidade
- Não homologar recovery write sem unidade separada e efeito controlado.
- Não atribuir commit-fonte ao 0.34 sem manifest/prova reprodutível.

## Entradas aceitas nesta unidade
- 1541/1542 — evidência histórica v64 do bloqueio live, agora fechada como etapa precedente.
- 1547 `docs/reconciliation/admin-observability-cpp-live-v67.json`.
- 1548 `tests/test_admin_observability_cpp_live_evidence.py`.
- 179 `skills/cloudiff/SKILL.md` — `cloudiff@0.1.23`, L032.
- 2 `competencias.yaml` — skill raiz 0.1.23.
- 9 `estado.md` — snapshot v67.
- 10 `manifesto.yaml` — contrato v67 e zona liberada.

## Próxima unidade
- T-031: diagnosticar onboarding atual em leitura.
- T-024/T-025 somente quando surgirem seus artefatos de desbloqueio.
