# Estado — 2026-08-28 — contrato v61

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a correção desta unidade não altera HTML, CSS, JS visual, textos, botões ou layout.
- O link congelado `Visão geral` (`?tab=resumo`) deve produzir o mesmo painel acadêmico canônico servido na raiz do Portal; o renderer administrativo legado não é contrato visual válido para esse alias.
- A promoção produtiva da correção `Visão geral` está homologada: live hash `1ae42e1e...`, `current` no candidato, `previous` no baseline `4407bd7c...`, raiz/alias/navigation equivalentes e verificador residente `errors=0`.
- Faro é o nó CloudIFF de papel `edge`; seu perfil deseja `portal-host`, mas o cutover do Portal ocorre somente após onboarding Faro e portões de portal shadow.
- O onboarding Faro está aceito: 4 vCPU online, identidade própria, PKI/NATS individual, agent não-root, heartbeat direto para Hospedagem, reconciliação/resiliência e rollback já possuem evidência mecânica.
- O heartbeat atual do Faro observa capabilities `inventory`, `health`, `telemetry-host`, `portal-host` e `agent-auto-update`; `build` e `runtime` continuam excluídas do perfil Faro.
- O caminho crítico Faro é `10.62.91.5 -> NATS 10.62.92.7:14222 -> cloudiff-control -> PostgreSQL`; Forja e Maurício não participam do heartbeat crítico.
- Releases de agent-skills permanecem imutáveis; o runtime Faro continua na release instalada `cloudiff@0.1.4`, enquanto a skill de projeto usada nesta unidade é `cloudiff@0.1.19`.

## Decisões superadas
- Salto obrigatório via `172.16.0.1` para acessar máquinas do laboratório — superado em 28/08/2026 pela nova orientação da TI comunicada pelo operador; acesso operacional passa a ser direto pelo conector Labiff, mantendo pfSense/MikroTik apenas como equipamentos de rede quando necessário.
- Faro bloqueado por `2/4 vCPU` — superado em 26/08/2026 após a TI ampliar a VM e o SO observar CPUs `0-3`.
- `portal-host` apenas desejada/não observada — superado pelo heartbeat PostgreSQL atual, que já anuncia `portal-host`; isso não equivale a cutover do Portal.
- Confiar apenas na árvore de uma release de skills já existente como prova do artefato recebido — superado na v45 pelo gate do TAR recebido.

## Decisões humanas pendentes
- Nenhuma decisão humana adicional para aceitar o nó Faro.
- Cutover definitivo do Portal para Faro permanece uma unidade posterior e deve respeitar os portões de portal shadow/FrozenPortalInterface; não foi executado implicitamente nesta unidade.

## Decisões fechadas nesta emenda
- NpmPublisher 0.10, RuntimeExecutor 0.17/0.24 e ArtifactEngine 0.27 estão identificados no live por release path, SHA-256, GNU BuildID, timestamp e toolchain, mas nenhum possui commit fonte comprovado.
- O histórico C++ disponível em todas as branches remotas começa em `2e869b7` de 24/08, depois das quatro instalações de 20–21/08; portanto não pode ser usado retroativamente como source commit dessas builds.
- Referência posterior de uma release no Git prova uso/continuidade, não a origem do binário. Releases futuras só recebem atribuição de source com manifesto local criptograficamente ligado ao binário ou build reproduzível independente com SHA idêntico.

## Pendências técnicas não humanas
- Os quatro binários antigos permanecem com `exact_source_commit: NAO DECLARADO`; a lacuna foi fechada como não recuperável pelas fontes disponíveis, não apagada por inferência.
- Releases futuras devem gerar `release-manifest.json` com source commit/tree, SHA-256, GNU BuildID, compiler, digest do comando de build e timestamp antes de promoção.
- T-014 política de retenção no 251 permanece não executada e deve abrir unidade própria.
- Dois dead-letters históricos de membership seguem pendentes de revisão somente leitura antes de replay.
- Ativação contínua de `cloudiff.v2.build.classic` em C++ continua dependente de gate próprio.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `T-018-proveniencia-binarios-cpp-live`, concluída; nenhuma zona de exclusão permanece ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.19` — skill raiz; L028 homologado.
- `desenvolvedor-de-software@14` — método PGH.
- `github-incremental-reconciliation@7` — reconciliação incremental de Git/skill/catálogo.
- `governanca-ontologica-de-skills@1.0.4` — governança da skill.
- `telemetry-data-visualization@2` — macro global; coletor indisponível.
- `platform-engineering` — procedência de release/binário e rastreabilidade de build.

## Falhas de portão por tipo de entrada
- `procedencia`: nenhum dos quatro binários antigos possui source manifest ou commit embutido; versões/release paths não satisfazem atribuição de fonte.
- `historico`: o primeiro commit C++ disponível é posterior às builds antigas, logo não pode ser tratado como origem delas.

## Divergências da última reconciliação
### Corrigidas
- Entrada 1535 centraliza release path, SHA-256, GNU BuildID, timestamps, toolchain e rollout dos quatro binários antigos.
- Foram pesquisadas todas as branches remotas, release dirs, journals, scripts sobreviventes, `/tmp`, `/home/cti` e metadados ELF sem encontrar commit fonte contemporâneo.
- Artifact v27 possui referência no commit `2e869b7`, mas ela é de 24/08 e a instalação é de 21/08; foi classificada como `post_build_reference_not_build_provenance`.
- Entrada 1536 impede promover versão/release/BuildID a source commit e fixa o gate de manifesto para futuras releases.
- `cloudiff@0.1.19` registra L028; `VISUAL_DIFF=NO`.

### Pendentes de autorização ou capacidade
- Nenhuma ação destrutiva ou troca de runtime foi executada.
- O `main` do CloudIFF permanece separado do branch auditável.

## Entradas aceitas nesta unidade
- 1535 `docs/reconciliation/cpp-live-binary-provenance-v61.json` — procedência observável consolidada.
- 1536 `tests/test_cpp_live_binary_provenance_evidence.py` — gate contra atribuição de source sem prova.
- 179 `skills/cloudiff/SKILL.md` — `cloudiff@0.1.19`, L028.
- 2 `competencias.yaml` — skill raiz 0.1.19.
- 9 `estado.md` — snapshot v61.
- 10 `manifesto.yaml` — contrato v61 e zona liberada.

## Próxima unidade
- T-014: formalizar política de retenção no 251 sem deleção automática por idade, com checksum e ownership como gates.
- Depois, continuar auditoria de `mcp-upload`, `secure-distribution` ou `admin-observability` pelo consumidor live.
