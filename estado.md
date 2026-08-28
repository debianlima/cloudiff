# Estado — 2026-08-28 — contrato v60

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a correção desta unidade não altera HTML, CSS, JS visual, textos, botões ou layout.
- O link congelado `Visão geral` (`?tab=resumo`) deve produzir o mesmo painel acadêmico canônico servido na raiz do Portal; o renderer administrativo legado não é contrato visual válido para esse alias.
- A promoção produtiva da correção `Visão geral` está homologada: live hash `1ae42e1e...`, `current` no candidato, `previous` no baseline `4407bd7c...`, raiz/alias/navigation equivalentes e verificador residente `errors=0`.
- Faro é o nó CloudIFF de papel `edge`; seu perfil deseja `portal-host`, mas o cutover do Portal ocorre somente após onboarding Faro e portões de portal shadow.
- O onboarding Faro está aceito: 4 vCPU online, identidade própria, PKI/NATS individual, agent não-root, heartbeat direto para Hospedagem, reconciliação/resiliência e rollback já possuem evidência mecânica.
- O heartbeat atual do Faro observa capabilities `inventory`, `health`, `telemetry-host`, `portal-host` e `agent-auto-update`; `build` e `runtime` continuam excluídas do perfil Faro.
- O caminho crítico Faro é `10.62.91.5 -> NATS 10.62.92.7:14222 -> cloudiff-control -> PostgreSQL`; Forja e Maurício não participam do heartbeat crítico.
- Releases de agent-skills permanecem imutáveis; o runtime Faro continua na release instalada `cloudiff@0.1.4`, enquanto a skill de projeto usada nesta unidade é `cloudiff@0.1.18`.

## Decisões superadas
- Salto obrigatório via `172.16.0.1` para acessar máquinas do laboratório — superado em 28/08/2026 pela nova orientação da TI comunicada pelo operador; acesso operacional passa a ser direto pelo conector Labiff, mantendo pfSense/MikroTik apenas como equipamentos de rede quando necessário.
- Faro bloqueado por `2/4 vCPU` — superado em 26/08/2026 após a TI ampliar a VM e o SO observar CPUs `0-3`.
- `portal-host` apenas desejada/não observada — superado pelo heartbeat PostgreSQL atual, que já anuncia `portal-host`; isso não equivale a cutover do Portal.
- Confiar apenas na árvore de uma release de skills já existente como prova do artefato recebido — superado na v45 pelo gate do TAR recebido.

## Decisões humanas pendentes
- Nenhuma decisão humana adicional para aceitar o nó Faro.
- Cutover definitivo do Portal para Faro permanece uma unidade posterior e deve respeitar os portões de portal shadow/FrozenPortalInterface; não foi executado implicitamente nesta unidade.

## Decisões fechadas nesta emenda
- `ArtifactEngine` C++ live `0.27.0-shadow` na Forja passou validação side-effect-free real; imagens, containers e resultados persistentes permaneceram com hashes idênticos.
- O ingress `cloudif-artifact-executor-v2.internal` é dedicado ao canary `classic-static-v2` e preserva escopo de token/rota; não substitui o host compartilhado legado.
- `cloudif-artifact-executor.internal` e o executor Python 18216 permanecem autoritativos para o fluxo compartilhado; `ClassicBuildWorker` C++ 0.27 é manual oneshot/inativo e o worker contínuo 0.15 não aceita `cloudiff.v2.build.classic`.

## Pendências técnicas não humanas
- Ativação contínua de `cloudiff.v2.build.classic` em C++ continua pendente de gate separado; não ampliar `CLOUDIFF_WORKER_ALLOWED_KINDS` sem canary de fila/lease/artifact/attestation.
- Procedência exata do binário `ArtifactEngine` live 0.27 permanece `NAO DECLARADO`; source atual do agente é 0.36.
- O executor Python compartilhado e o Python BuildBroker não podem ser retirados enquanto continuarem autoridade contratual/live.
- T-014 política de retenção no 251 permanece não executada e deve abrir unidade própria.
- Dois dead-letters históricos de membership seguem pendentes de revisão somente leitura antes de qualquer replay.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `T-017-artifact-executor-cpp-authority`, concluída; nenhuma zona de exclusão permanece ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.18` — skill raiz; L027 homologado.
- `desenvolvedor-de-software@14` — método PGH.
- `github-incremental-reconciliation@7` — reconciliação incremental.
- `governanca-ontologica-de-skills@1.0.4` — governança da skill.
- `telemetry-data-visualization@2` — macro global; coletor indisponível.
- `platform-engineering` / `operational-ui-truth` — prova de ingress, consumidor e efeito live.

## Falhas de portão por tipo de entrada
- `autoridade`: C++ live/ingress dedicado não é autoridade geral; host compartilhado permanece Python.
- `worker`: worker contínuo ativo exclui classic; canary 0.27 está inativo/manual.
- `procedencia`: live artifact 0.27 não foi ligado a commit fonte exato.

## Divergências da última reconciliação
### Corrigidas
- Entrada 1533 registra coexistência real Python 18216 + C++ 18226 e o ingress dedicado v2 18228.
- Validação live real de `laboratorio-de-hardware` retornou 200/valid/sideEffectFree sem alterar hashes de imagens, containers ou resultados.
- Ingress dedicado desde Hospedagem retornou 404 para GET, 403 para token classic fora do profile e 400 pre-effect para fonte inválida, provando escopo sem build.
- PostgreSQL não possuía job clássico ativo; canary worker estava inativo e worker contínuo aceitava apenas noop/fail_once.
- `cloudiff@0.1.18` registra L027; `VISUAL_DIFF=NO`.

### Pendentes de autorização ou capacidade
- Habilitar classic no worker contínuo exige unidade/gate próprio; nenhuma ativação foi feita nesta auditoria.
- O `main` continua separado do branch auditável.

## Entradas aceitas nesta unidade
- 1533 `docs/reconciliation/artifact-executor-cpp-authority-v60.json` — evidência live de autoridade parcial.
- 1534 `tests/test_artifact_executor_cpp_authority_evidence.py` — gate contra overclaim.
- 179 `skills/cloudiff/SKILL.md` — `cloudiff@0.1.18`, L027.
- 2 `competencias.yaml` — skill raiz 0.1.18.
- 9 `estado.md` — snapshot v60.
- 10 `manifesto.yaml` — contrato v60 e zona liberada.

## Próxima unidade
- T-014: formalizar política de retenção no 251 sem deleção automática por idade e com checksum/ownership como gates.
- T-017 seguinte: auditar `mcp-upload`, `secure-distribution` ou `admin-observability` conforme consumo live, sem inferir migração por presença de unit.
