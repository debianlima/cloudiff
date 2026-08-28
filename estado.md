# Estado — 2026-08-27 — contrato v54

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a correção desta unidade não altera HTML, CSS, JS visual, textos, botões ou layout.
- O link congelado `Visão geral` (`?tab=resumo`) deve produzir o mesmo painel acadêmico canônico servido na raiz do Portal; o renderer administrativo legado não é contrato visual válido para esse alias.
- Faro é o nó CloudIFF de papel `edge`; seu perfil deseja `portal-host`, mas o cutover do Portal ocorre somente após onboarding Faro e portões de portal shadow.
- O onboarding Faro está aceito: 4 vCPU online, identidade própria, PKI/NATS individual, agent não-root, heartbeat direto para Hospedagem, reconciliação/resiliência e rollback já possuem evidência mecânica.
- O heartbeat atual do Faro observa capabilities `inventory`, `health`, `telemetry-host`, `portal-host` e `agent-auto-update`; `build` e `runtime` continuam excluídas do perfil Faro.
- O caminho crítico Faro é `10.62.91.5 -> NATS 10.62.92.7:14222 -> cloudiff-control -> PostgreSQL`; Forja e Maurício não participam do heartbeat crítico.
- Releases de agent-skills permanecem imutáveis; o runtime Faro continua na release instalada `cloudiff@0.1.4`, enquanto a skill de projeto usada nesta unidade é `cloudiff@0.1.11`.

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
- Permanecem entradas `pendente`/`preexistente` fora desta unidade no contrato v54; a liberação global do projeto deve selecionar quais delas são release-blocking antes de declarar release final.
- LegacyRetirement continua separado e qualquer retirada destrutiva exige seus próprios gates e autorização final.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `ui-action-map-project-resume`, concluída em `2026-08-27T23:12:00-03:00`; nenhuma zona de exclusão permanece ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.11` — skill raiz; nenhuma atualização nesta unidade porque o comportamento homologado já correspondia ao contrato.
- `desenvolvedor-de-software@14` — método PGH para auditoria de tela.
- `github-incremental-reconciliation@7` — reconciliação de branch/estrutura.
- `telemetry-data-visualization@2` — macro global; coletor executável continua indisponível nesta árvore.
- `operational-ui-truth@1` / `navegacao` — prova tela ↔ efeito fora da própria interface.

## Falhas de portão por tipo de entrada
- `teste`: o primeiro harness de retomada não possuía as tabelas auxiliares `project_public_ids`/`project_publications`; elas foram declaradas somente no SQLite temporário do portão.
- Nenhuma divergência funcional foi encontrada em `resume_initial_publication` ou no ramo resume-only do worker.

## Divergências da última reconciliação
### Corrigidas
- Entrada 1524 executa o botão **Retomar publicação** pelo handler final: proprietário recebe 303 e job com `action=resume_initial_publication`, `create_repo=0`, `setup_komodo=0`, runtime/public number existentes e projeto preservado.
- Não proprietário e CSRF ausente não criam job.
- O job real é entregue ao worker controlado, que executa somente `cloudif-project-initial-publish.py`, marca `resume_only=true` e enfileira `project.membership.changed` após sucesso; tenant policy, backup e provisionador geral não são executados.
- Regressão do Portal: 1034/1034; `validate-repository`, `git diff --check` e `VISUAL_DIFF=NO`: PASS.

### Pendentes de autorização ou capacidade
- `main` do Cloudiff permanece em skill 0.1.5; esta auditoria continua no branch auditável e catálogo por commit específico.
- Runtime de produção da `Visão geral` continua sem promoção; entradas 1515/1516 permanecem `em_curso` até shadow real verde.
- Primeiro salto `172.16.0.1` continua bloqueando homologação remota enquanto o plano administrativo não responder.

## Entradas aceitas nesta unidade
- 1524 `portal/tests/test_project_resume_action_effect.py` — handler + worker resume-only homologados por job/command/reconciliação independentes.
- 9 `estado.md` — snapshot da unidade.
- 10 `manifesto.yaml` — contrato v54 e zona liberada.

## Próxima unidade
- Provar que o fluxo W/H/P preserva a **mesma identidade de artefato** entre candidato homologado e Produção, incluindo rejeição de imagem/digest divergente antes da fila.
- Depois, auditar o worker de publicação contra esse binding sem alterar o wizard.
- Quando o plano de gestão do pfSense voltar, repetir shadow da `Visão geral`; somente shadow verde autoriza promoção.
