# Estado — 2026-08-27 — contrato v53

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
- Permanecem entradas `pendente`/`preexistente` fora desta unidade no contrato v53; a liberação global do projeto deve selecionar quais delas são release-blocking antes de declarar release final.
- LegacyRetirement continua separado e qualquer retirada destrutiva exige seus próprios gates e autorização final.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `ui-action-map-project-create`, concluída em `2026-08-27T23:12:00-03:00`; nenhuma zona de exclusão permanece ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.11` — skill raiz; L020 homologado nesta unidade.
- `desenvolvedor-de-software@14` — método PGH para auditoria de tela.
- `github-incremental-reconciliation@7` — reconciliação incremental da skill/catálogo.
- `governanca-ontologica-de-skills@1.0.4` — governança da versão da skill.
- `telemetry-data-visualization@2` — macro global; coletor executável continua indisponível nesta árvore.
- `operational-ui-truth@1` / `navegacao` — prova tela ↔ efeito fora da própria interface.

## Falhas de portão por tipo de entrada
- `ui-compat`: o negativo de runtime não homologado devolvia erro 500, mas o portão observou que `projects` e ACL do dono já estavam persistidos; validação ocorria tarde demais.
- `teste`: em discovery completo, um teste anterior deixava stub de `cloudif_delete_git_komodo_action` em `sys.modules`; o novo portão foi isolado para carregar o módulo real e restaurar o estado anterior, sem mudar produção.

## Divergências da última reconciliação
### Corrigidas
- Runtime, PHP e keepalive são validados antes de abrir a transação de escrita de `upsert_project()`.
- Pedido válido pelo handler final assíncrono retorna 202 e produz projeto, ACL do proprietário, job JSON durável e evento `project.created` com runtime/layout.
- Runtime inválido e CSRF ausente produzem efeito zero em projeto, ACL, job e reconciliação.
- `cloudiff@0.1.11` registra L020 para preservar validação antes da primeira mutação na migração C++23.
- Regressão do Portal: 1030/1030; `validate-repository`, `git diff --check` e `VISUAL_DIFF=NO`: PASS.

### Pendentes de autorização ou capacidade
- `main` do Cloudiff ainda contém skill 0.1.5; as homologações desta auditoria vivem no branch `audit/ui-overview-alias-fix` e no catálogo por commit específico. Nenhum merge para `main` foi inferido.
- Runtime de produção da `Visão geral` continua sem promoção; entradas 1515/1516 permanecem `em_curso` até shadow real verde.
- Primeiro salto `172.16.0.1` continua como bloqueio operacional enquanto o plano administrativo não responder.

## Entradas aceitas nesta unidade
- 651 `components/control-plane/srv/cloudif/lib/cloudif_project_action_safe.py` — validação determinística movida antes da primeira escrita.
- 1523 `portal/tests/test_project_create_action_effect.py` — 202 assíncrono, SQLite/ACL/job/reconciliação e negativos de efeito zero provados.
- 179 `skills/cloudiff/SKILL.md` — `cloudiff@0.1.11`, L020 homologado.
- 2 `competencias.yaml` — versão da skill raiz reconciliada.
- 9 `estado.md` — snapshot da unidade.
- 10 `manifesto.yaml` — contrato v53 e zona liberada.

## Próxima unidade
- Auditar a **retomada da publicação inicial** (`resume_initial_publication`) por efeito em job durável e reconciliação, garantindo que não repita infraestrutura já pronta.
- Depois, completar o worker de provisionamento com prova de que H/P e publicação inicial usam os mesmos artefatos/identidades homologados.
- Quando o plano de gestão do pfSense voltar, repetir shadow da `Visão geral`; somente shadow verde autoriza promoção.
