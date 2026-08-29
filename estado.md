# Estado — 2026-08-28 — contrato v70

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a correção desta unidade não altera HTML, CSS, JS visual, textos, botões ou layout.
- O link congelado `Visão geral` (`?tab=resumo`) deve produzir o mesmo painel acadêmico canônico servido na raiz do Portal; o renderer administrativo legado não é contrato visual válido para esse alias.
- A promoção produtiva da correção `Visão geral` está homologada: live hash `1ae42e1e...`, `current` no candidato, `previous` no baseline `4407bd7c...`, raiz/alias/navigation equivalentes e verificador residente `errors=0`.
- Faro é o nó CloudIFF de papel `edge`; seu perfil deseja `portal-host`, mas o cutover do Portal ocorre somente após onboarding Faro e portões de portal shadow.
- O onboarding Faro está aceito: 4 vCPU online, identidade própria, PKI/NATS individual, agent não-root, heartbeat direto para Hospedagem, reconciliação/resiliência e rollback já possuem evidência mecânica.
- O heartbeat atual do Faro observa capabilities `inventory`, `health`, `telemetry-host`, `portal-host` e `agent-auto-update`; `build` e `runtime` continuam excluídas do perfil Faro.
- O caminho crítico Faro é `10.62.91.5 -> NATS 10.62.92.7:14222 -> cloudiff-control -> PostgreSQL`; Forja e Maurício não participam do heartbeat crítico.
- Releases de agent-skills permanecem imutáveis; o runtime Faro continua na release instalada `cloudiff@0.1.4`, enquanto a skill de projeto usada nesta unidade é `cloudiff@0.1.26`.

## Decisões superadas
- Salto obrigatório via `172.16.0.1` para acessar máquinas do laboratório — superado em 28/08/2026 pela nova orientação da TI comunicada pelo operador; acesso operacional passa a ser direto pelo conector Labiff, mantendo pfSense/MikroTik apenas como equipamentos de rede quando necessário.
- Faro bloqueado por `2/4 vCPU` — superado em 26/08/2026 após a TI ampliar a VM e o SO observar CPUs `0-3`.
- `portal-host` apenas desejada/não observada — superado pelo heartbeat PostgreSQL atual, que já anuncia `portal-host`; isso não equivale a cutover do Portal.
- Confiar apenas na árvore de uma release de skills já existente como prova do artefato recebido — superado na v45 pelo gate do TAR recebido.

## Decisões humanas pendentes
- Nenhuma decisão humana adicional para aceitar o nó Faro.
- Cutover definitivo do Portal para Faro permanece uma unidade posterior e deve respeitar os portões de portal shadow/FrozenPortalInterface; não foi executado implicitamente nesta unidade.

## Decisões fechadas nesta emenda
- T-036 diagnosticou `cloudif-ui-security-review.service` em failed sem restart: exit 1 é causado por 5 assertions de layout/role markers obsoletos no `cloudif-ui-security-tests.py`.
- O report atual mantém professor/admin HTTP 200, skip-link/aria/logout e todos os headers/policies de segurança esperados em PASS; não há prova de regressão desses controles.
- O Portal live usa `enterprise-nav/ui143-nav`, `profile-chip` e `portal-hero`, enquanto o gate exige `nav/app/page/profile-card/profile-role` e `Administração do AD`.
- O gate live e o versionado têm o mesmo SHA; `portal/tests/test_ui_security_gate_contract.py` também institucionaliza os marcadores antigos, portanto a suíte estática pode ficar verde enquanto a revisão periódica live falha.
- Houve restart do Portal às 04:35:43 UTC entre o último UI subtest 20/20 observado e a primeira série 5-failures, mas T-036 não declarou o restart como causa raiz do drift.
- Nenhuma alteração visual, gate live ou restart foi executado. T-036R fica bloqueada por decisão humana para mudar semântica de aceitação do security gate em produção.

## Pendências técnicas não humanas
- T-034R BLOCKED: hardening/rotação de `NPM data/keys.json` requer autorização humana.
- T-036R BLOCKED: corrigir o contrato do UI security gate e reexecutar a oneshot requer decisão humana sobre semântica do gate live.
- T-028 READY: investigar read-only o gatilho externo do reboot pfSense; não tocar no pfSense.
- T-029 READY: arquitetura de redução de SPOF, sem implantação.
- T-030/T-033/T-035 READY: documentação, observabilidade e warning NPM.
- T-022/T-023/T-024/T-025/T-032 permanecem dependentes de wiring/releases externas.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `T-036-ui-security-review-failed-diagnostico`, concluída; nenhuma zona de exclusão permanece ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.26` — skill raiz; L035 homologado.
- `desenvolvedor-de-software@14` — método PGH.
- `github-incremental-reconciliation@7` — reconciliação incremental.
- `governanca-ontologica-de-skills@1.0.4` — governança.
- `telemetry-data-visualization@2` — macro global; coletor indisponível.

## Falhas de portão por tipo de entrada
- `ui-security-review`: contrato live prende classes/labels antigos e falha 5/20 apesar de HTTP/headers de segurança verdes.
- `contract-test`: teste estático do gate valida os mesmos marcadores obsoletos e impede detectar o drift antes do runtime.

## Divergências da última reconciliação
### Corrigidas
- Entrada 1556 fixa a causa observada da unit failed sem confundir drift UI com regressão de headers.
- Entrada 1557 impede overclaim de segurança e exige registrar que o próprio contract test está stale.
- `cloudiff@0.1.26` registra L035; `VISUAL_DIFF=NO`.

### Pendentes de autorização ou capacidade
- T-036R: alterar critérios do gate e executar/deployar a correção live somente após decisão humana.
- T-034R: hardening da chave JWT NPM também aguarda autorização humana.

## Entradas aceitas nesta unidade
- 1556 `docs/reconciliation/ui-security-review-stale-gate-v70.json`.
- 1557 `tests/test_ui_security_review_stale_gate_evidence.py`.
- 179 `skills/cloudiff/SKILL.md` — `cloudiff@0.1.26`, L035.
- 2 `competencias.yaml` — skill raiz 0.1.26.
- 9 `estado.md` — snapshot v70.
- 10 `manifesto.yaml` — contrato v70 e zona liberada.

## Próxima unidade
- T-028: investigação read-only do hypervisor, sem tocar no pfSense.
- T-029: pré-estudo/arquitetura de redundância pfSense, sem implantação.
