# Estado — 2026-08-28 — contrato v62

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a correção desta unidade não altera HTML, CSS, JS visual, textos, botões ou layout.
- O link congelado `Visão geral` (`?tab=resumo`) deve produzir o mesmo painel acadêmico canônico servido na raiz do Portal; o renderer administrativo legado não é contrato visual válido para esse alias.
- A promoção produtiva da correção `Visão geral` está homologada: live hash `1ae42e1e...`, `current` no candidato, `previous` no baseline `4407bd7c...`, raiz/alias/navigation equivalentes e verificador residente `errors=0`.
- Faro é o nó CloudIFF de papel `edge`; seu perfil deseja `portal-host`, mas o cutover do Portal ocorre somente após onboarding Faro e portões de portal shadow.
- O onboarding Faro está aceito: 4 vCPU online, identidade própria, PKI/NATS individual, agent não-root, heartbeat direto para Hospedagem, reconciliação/resiliência e rollback já possuem evidência mecânica.
- O heartbeat atual do Faro observa capabilities `inventory`, `health`, `telemetry-host`, `portal-host` e `agent-auto-update`; `build` e `runtime` continuam excluídas do perfil Faro.
- O caminho crítico Faro é `10.62.91.5 -> NATS 10.62.92.7:14222 -> cloudiff-control -> PostgreSQL`; Forja e Maurício não participam do heartbeat crítico.
- Releases de agent-skills permanecem imutáveis; o runtime Faro continua na release instalada `cloudiff@0.1.4`, enquanto a skill de projeto usada nesta unidade é `cloudiff@0.1.20`.

## Decisões superadas
- Salto obrigatório via `172.16.0.1` para acessar máquinas do laboratório — superado em 28/08/2026 pela nova orientação da TI comunicada pelo operador; acesso operacional passa a ser direto pelo conector Labiff, mantendo pfSense/MikroTik apenas como equipamentos de rede quando necessário.
- Faro bloqueado por `2/4 vCPU` — superado em 26/08/2026 após a TI ampliar a VM e o SO observar CPUs `0-3`.
- `portal-host` apenas desejada/não observada — superado pelo heartbeat PostgreSQL atual, que já anuncia `portal-host`; isso não equivale a cutover do Portal.
- Confiar apenas na árvore de uma release de skills já existente como prova do artefato recebido — superado na v45 pelo gate do TAR recebido.

## Decisões humanas pendentes
- Nenhuma decisão humana adicional para aceitar o nó Faro.
- Cutover definitivo do Portal para Faro permanece uma unidade posterior e deve respeitar os portões de portal shadow/FrozenPortalInterface; não foi executado implicitamente nesta unidade.

## Decisões fechadas nesta emenda
- `mcp-upload` C++ live `0.20.0-shadow` é um planner shadow side-effect-free em 18234; passou auth e fallback path-like sem acessar filesystem/rede nem vazar caminho local.
- O MCP Gateway Python live não referencia o planner C++ e continua sendo autoridade para exposição/autenticação/seleção de fallback e dispatch das ferramentas de upload; o Workspace Broker continua autoridade dos efeitos.
- O gateway live é uma projeção derivada versionada: source base `948e...`, patch upload `b218...`, patch download `f332...`; o SHA live é `f332...`, portanto a diferença branch/live tem linhagem comprovada.
- Reinício do serviço C++ em 28/08 reutilizou release `20260820-v20-mcp-upload-shadow` com binário de 21/08; não é release nova nem atende T-023.

## Pendências técnicas não humanas
- T-023 permanece bloqueada até o fluxo de migração produzir uma release nova com `release-manifest.json`; reinícios de releases antigas não contam.
- `mcp-upload` C++ não pode ser declarado autoridade enquanto o gateway live não possuir wiring explícito para 18234 ou equivalente e os efeitos continuarem no Python/Workspace Broker.
- O commit fonte exato do binário live mcp-upload 0.20 permanece `NAO DECLARADO`; source atual do agente é 0.36.
- T-014 política de retenção no 251 permanece READY e não executada.
- Dois dead-letters históricos de membership seguem pendentes de revisão somente leitura.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `T-019-mcp-upload-cpp-audit`, concluída; nenhuma zona de exclusão permanece ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.20` — skill raiz; L029 homologado.
- `desenvolvedor-de-software@14` — método PGH.
- `github-incremental-reconciliation@7` — reconciliação incremental.
- `governanca-ontologica-de-skills@1.0.4` — governança da skill.
- `telemetry-data-visualization@2` — macro global; coletor indisponível.
- `platform-engineering` / `operational-ui-truth` — prova de consumidor, planner e efeito real.

## Falhas de portão por tipo de entrada
- `autoridade`: planner C++ saudável não é consumido pelo gateway live; efeito de upload segue Python/Workspace Broker.
- `procedencia`: binário mcp-upload 0.20 não possui `release-manifest.json` nem commit fonte provado.
- `release`: restart em 28/08 reutilizou binário antigo e não satisfaz o gate T-023.

## Divergências da última reconciliação
### Corrigidas
- Entrada 1537 registra C++ 0.20 ativo em 18234, auth 401 negativa e plan 200 side-effect-free para input path-like sem vazamento do caminho.
- `tools/list` do gateway live retornou 152 ferramentas e confirmou as cinco ferramentas de upload; source live possui zero referência ao planner C++.
- A aparente diferença entre `current-app` e release gateway foi reconciliada pela cadeia de patches versionada `948e... -> b218... -> f332...`, cujo SHA final coincide com o live.
- Entrada 1538 impede declarar upload MCP migrado enquanto o consumidor e os efeitos permanecerem Python.
- `cloudiff@0.1.20` registra L029; nenhum HTML/CSS/JS visual foi alterado (`VISUAL_DIFF=NO`).

### Pendentes de autorização ou capacidade
- Wiring do gateway para o planner C++ pertence ao fluxo de migração e exige unidade/gate próprio antes de alterar autoridade.
- O `main` do CloudIFF continua separado do branch auditável.

## Entradas aceitas nesta unidade
- 1537 `docs/reconciliation/mcp-upload-cpp-authority-v62.json` — evidência live de planner/consumer/linhagem.
- 1538 `tests/test_mcp_upload_cpp_authority_evidence.py` — gate contra overclaim de migração.
- 179 `skills/cloudiff/SKILL.md` — `cloudiff@0.1.20`, L029.
- 2 `competencias.yaml` — skill raiz 0.1.20.
- 9 `estado.md` — snapshot v62.
- 10 `manifesto.yaml` — contrato v62 e zona liberada.

## Próxima unidade
- T-014: formalizar política de retenção no 251 sem deleção automática por idade, com checksum e ownership como gates.
- Depois, auditar `secure-distribution` ou `admin-observability` conforme consumo live.
