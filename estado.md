# Estado — 2026-08-28 — contrato v63

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a correção desta unidade não altera HTML, CSS, JS visual, textos, botões ou layout.
- O link congelado `Visão geral` (`?tab=resumo`) deve produzir o mesmo painel acadêmico canônico servido na raiz do Portal; o renderer administrativo legado não é contrato visual válido para esse alias.
- A promoção produtiva da correção `Visão geral` está homologada: live hash `1ae42e1e...`, `current` no candidato, `previous` no baseline `4407bd7c...`, raiz/alias/navigation equivalentes e verificador residente `errors=0`.
- Faro é o nó CloudIFF de papel `edge`; seu perfil deseja `portal-host`, mas o cutover do Portal ocorre somente após onboarding Faro e portões de portal shadow.
- O onboarding Faro está aceito: 4 vCPU online, identidade própria, PKI/NATS individual, agent não-root, heartbeat direto para Hospedagem, reconciliação/resiliência e rollback já possuem evidência mecânica.
- O heartbeat atual do Faro observa capabilities `inventory`, `health`, `telemetry-host`, `portal-host` e `agent-auto-update`; `build` e `runtime` continuam excluídas do perfil Faro.
- O caminho crítico Faro é `10.62.91.5 -> NATS 10.62.92.7:14222 -> cloudiff-control -> PostgreSQL`; Forja e Maurício não participam do heartbeat crítico.
- Releases de agent-skills permanecem imutáveis; o runtime Faro continua na release instalada `cloudiff@0.1.4`, enquanto a skill de projeto usada nesta unidade é `cloudiff@0.1.21`.

## Decisões superadas
- Salto obrigatório via `172.16.0.1` para acessar máquinas do laboratório — superado em 28/08/2026 pela nova orientação da TI comunicada pelo operador; acesso operacional passa a ser direto pelo conector Labiff, mantendo pfSense/MikroTik apenas como equipamentos de rede quando necessário.
- Faro bloqueado por `2/4 vCPU` — superado em 26/08/2026 após a TI ampliar a VM e o SO observar CPUs `0-3`.
- `portal-host` apenas desejada/não observada — superado pelo heartbeat PostgreSQL atual, que já anuncia `portal-host`; isso não equivale a cutover do Portal.
- Confiar apenas na árvore de uma release de skills já existente como prova do artefato recebido — superado na v45 pelo gate do TAR recebido.

## Decisões humanas pendentes
- Nenhuma decisão humana adicional para aceitar o nó Faro.
- Cutover definitivo do Portal para Faro permanece uma unidade posterior e deve respeitar os portões de portal shadow/FrozenPortalInterface; não foi executado implicitamente nesta unidade.

## Decisões fechadas nesta emenda
- `SecureDistributionProvider` C++ live `0.22.0-shadow` é autoridade real e consumida para a coleção `nats-server-cert`: NPM → 18240 → cert-sync da Hospedagem.
- A fronteira permanece explícita: provider faz distribuição read-only/capability/generation; `cloudiff-v2-cert-sync` valida cert/key, instala localmente e sinaliza NATS quando há mudança.
- A auditoria validou manifest e somente `fullchain.pem`; `privkey.pem` não foi requisitada. Faro foi negado com 403 no NPM e não recebe capability da coleção.
- Capability provider é root-only, armazena apenas hash SHA-256 do token e exige audience, expiry, collection scope e generation precondition; token bruto permanece root-only no consumidor.

## Pendências técnicas não humanas
- O commit-fonte exato do SecureDistribution 0.22 permanece `NAO DECLARADO`; release de 21/08 contém binário/config, mas não `release-manifest.json`.
- T-023 permanece bloqueada até existir release realmente nova com manifesto de procedência; restart do v22 em 28/08 não conta.
- T-024 wiring futuro do mcp-upload continua READY; planner C++ ainda não é consumido pelo gateway.
- T-014 política de retenção no 251 permanece READY e não executada.
- Dois dead-letters históricos de membership seguem pendentes de revisão somente leitura.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `T-020-secure-distribution-cpp-audit`, concluída; nenhuma zona de exclusão permanece ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.21` — skill raiz; L030 homologado.
- `desenvolvedor-de-software@14` — método PGH.
- `github-incremental-reconciliation@7` — reconciliação incremental.
- `governanca-ontologica-de-skills@1.0.4` — governança da skill.
- `telemetry-data-visualization@2` — macro global; coletor indisponível.
- `platform-engineering` / `operational-ui-truth` — prova de rota, capability, provider, consumer e efeito separado.

## Falhas de portão por tipo de entrada
- `procedencia`: provider C++ 0.22 é funcionalmente autoritativo, mas não possui commit-fonte comprovado; autoridade de runtime não apaga lacuna de build provenance.
- `segredo`: a coleção inclui `privkey.pem`; auditorias devem validar manifest/generation/fullchain sem requisitar chave privada salvo unidade explicitamente autorizada.

## Divergências da última reconciliação
### Corrigidas
- Entrada 1539 registra provider C++ 0.22 ativo em 10.62.91.3:18240, capability não expirada, rota NPM GET/source-allow e consumer timer ativo na Hospedagem.
- Probe autenticado provou auth inválida 403, query token 400, objeto sem generation 428, manifest 200 e fullchain com SHA/generation/fingerprint equivalentes ao local.
- Faro recebeu 403 pelo NPM; `privkey.pem` não foi requisitada durante a auditoria.
- Script cert-sync live tem SHA idêntico ao artefato versionado e a última execução terminou 0 com `certificate_unchanged`.
- Entrada 1540 transforma autoridade read-only, fronteira de segredo e separação provider/install em gate mecânico.
- `cloudiff@0.1.21` registra L030; `VISUAL_DIFF=NO`.

### Pendentes de autorização ou capacidade
- Nenhuma alteração na capability, generation, certificado, chave ou NATS foi realizada nesta unidade.
- O `main` do CloudIFF continua separado do branch auditável.

## Entradas aceitas nesta unidade
- 1539 `docs/reconciliation/secure-distribution-cpp-authority-v63.json` — evidência live provider/rota/capability/consumer.
- 1540 `tests/test_secure_distribution_cpp_authority_evidence.py` — gate de autoridade e segredo.
- 179 `skills/cloudiff/SKILL.md` — `cloudiff@0.1.21`, L030.
- 2 `competencias.yaml` — skill raiz 0.1.21.
- 9 `estado.md` — snapshot v63.
- 10 `manifesto.yaml` — contrato v63 e zona liberada.

## Próxima unidade
- T-024: auditar qualquer wiring futuro do `mcp-upload` C++ somente quando aparecer no consumidor live; não inventar ligação em antecipação.
- T-014 segue READY: formalizar política de retenção no 251 sem deleção automática por idade.
- T-021 segue READY: auditar `admin-observability` C++ pela utilização real do Portal/operadores.
