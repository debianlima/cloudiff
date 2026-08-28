# Estado — 2026-08-27 — contrato v56

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a correção desta unidade não altera HTML, CSS, JS visual, textos, botões ou layout.
- O link congelado `Visão geral` (`?tab=resumo`) deve produzir o mesmo painel acadêmico canônico servido na raiz do Portal; o renderer administrativo legado não é contrato visual válido para esse alias.
- Faro é o nó CloudIFF de papel `edge`; seu perfil deseja `portal-host`, mas o cutover do Portal ocorre somente após onboarding Faro e portões de portal shadow.
- O onboarding Faro está aceito: 4 vCPU online, identidade própria, PKI/NATS individual, agent não-root, heartbeat direto para Hospedagem, reconciliação/resiliência e rollback já possuem evidência mecânica.
- O heartbeat atual do Faro observa capabilities `inventory`, `health`, `telemetry-host`, `portal-host` e `agent-auto-update`; `build` e `runtime` continuam excluídas do perfil Faro.
- O caminho crítico Faro é `10.62.91.5 -> NATS 10.62.92.7:14222 -> cloudiff-control -> PostgreSQL`; Forja e Maurício não participam do heartbeat crítico.
- Releases de agent-skills permanecem imutáveis; o runtime Faro continua na release instalada `cloudiff@0.1.4`, enquanto a skill de projeto usada nesta unidade é `cloudiff@0.1.12`.

## Decisões superadas
- Faro bloqueado por `2/4 vCPU` — superado em 26/08/2026 após a TI ampliar a VM e o SO observar CPUs `0-3`.
- `portal-host` apenas desejada/não observada — superado pelo heartbeat PostgreSQL atual, que já anuncia `portal-host`; isso não equivale a cutover do Portal.
- Confiar apenas na árvore de uma release de skills já existente como prova do artefato recebido — superado na v45 pelo gate do TAR recebido.

## Decisões humanas pendentes
- Nenhuma decisão humana adicional para aceitar o nó Faro.
- Cutover definitivo do Portal para Faro permanece uma unidade posterior e deve respeitar os portões de portal shadow/FrozenPortalInterface; não foi executado implicitamente nesta unidade.

## Decisões fechadas nesta emenda
- Faro atende ao perfil de recurso `4 vCPU / 8 GiB configurados / 200 GiB disco`; os três resource gates estão `pass`.
- `FARO-T19` passou e a etapa `acceptance` mudou de `partially_verified` para `verified`.

## Pendências técnicas não humanas
- O host Faro mantém `fwupd-refresh.service` falho por indisponibilidade de egress para o serviço externo; o verificador residente retorna `errors=0 warnings=1`. Isso não afeta o runtime CloudIFF/NATS.
- O inventário de máquina ainda precisa refletir Docker/cAdvisor presentes no Faro; máquina vence o inventário e a reconciliação é a próxima correção de ambiente desta mesma entrega.
- Permanecem entradas `pendente`/`preexistente` fora desta unidade no contrato v56; a liberação global do projeto deve selecionar quais delas são release-blocking antes de declarar release final.
- LegacyRetirement continua separado e qualquer retirada destrutiva exige seus próprios gates e autorização final.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `release-approval-finalization-failure`, concluída em perfil `terminal` íntegro; nenhuma zona de exclusão permanece ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.12` — skill raiz; L021 homologado nesta unidade.
- `desenvolvedor-de-software@14` — método PGH.
- `github-incremental-reconciliation@7` — reconciliação incremental da skill/catálogo.
- `governanca-ontologica-de-skills@1.0.4` — governança da versão da skill.
- `telemetry-data-visualization@2` — macro global; coletor executável indisponível, medida classificada como `indisponivel`.
- `operational-ui-truth@1` — efeito observado fora da interface.

## Falhas de portão por tipo de entrada
- `backend-integracao`: resposta 503 de `finalize` depois de publish fazia o job cair em `failed` mesmo quando a mesma reserva já estava `consumed` na releitura.
- `backend-integracao`: quando a aprovação ainda estava `reserved`, o `except` chamava `release` depois do efeito crítico já aplicado, reabrindo autorização para possível reaplicação.

## Divergências da última reconciliação
### Corrigidas
- Após publish, `finalize` sem resposta útil provoca releitura independente de `/v1/approvals?status=all` e só considera sucesso se `status=consumed` pertencer ao mesmo `reservation_id`.
- Se a mesma reserva permanece não consumida, job e `production_activation_requests` passam a `deployed_unfinalized`, passo `finalization_pending`, sem `release` e sem novo publish.
- Jobs `deployed_unfinalized` não são reclamados por `claim_next_job()`, evitando duplicação do side effect.
- `cloudiff@0.1.12` registra L021 para preservar esse invariante na migração C++23.
- Regressão do Portal: 1038/1038; `validate-repository`, `git diff --check`, projeções idênticas e `VISUAL_DIFF=NO`: PASS.

### Pendentes de autorização ou capacidade
- O `main` do Cloudiff permanece separado do branch auditável; nenhum merge foi inferido.
- A promoção produtiva de `Visão geral` continua bloqueada enquanto o primeiro salto administrativo não estiver disponível para repetir o shadow.
- A VM MCP Work foi registrada externamente no perfil `registro`; novos commits desta auditoria usam apenas máquina com inventário residente íntegro.

## Entradas aceitas nesta unidade
- 393 `components/control-plane/current-apps/portal-current/cloudif_portal_publications.py` — estado pós-publish/finalize reconciliado.
- 648 `components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py` — projeção idêntica reconciliada.
- 1526 `portal/tests/test_release_finalize_failure_effect.py` — resposta perdida e finalize pendente provados por execução.
- 179 `skills/cloudiff/SKILL.md` — `cloudiff@0.1.12`, L021 homologado.
- 2 `competencias.yaml` — versão da skill raiz reconciliada.
- 9 `estado.md` — snapshot da unidade.
- 10 `manifesto.yaml` — contrato v56 e zona liberada.

## Próxima unidade
- Auditar a paridade dos agentes já migrados para C++23 contra os contratos consumidos pelas superfícies congeladas, começando por publicação/reconciliação e sem benchmark/simulação fora da máquina Samba4 autorizada.
- Quando o primeiro salto administrativo voltar, repetir o shadow versionado de `Visão geral`; somente shadow verde autoriza promoção.
