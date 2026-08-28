# Estado — 2026-08-27 — contrato v52

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a correção desta unidade não altera HTML, CSS, JS visual, textos, botões ou layout.
- O link congelado `Visão geral` (`?tab=resumo`) deve produzir o mesmo painel acadêmico canônico servido na raiz do Portal; o renderer administrativo legado não é contrato visual válido para esse alias.
- Faro é o nó CloudIFF de papel `edge`; seu perfil deseja `portal-host`, mas o cutover do Portal ocorre somente após onboarding Faro e portões de portal shadow.
- O onboarding Faro está aceito: 4 vCPU online, identidade própria, PKI/NATS individual, agent não-root, heartbeat direto para Hospedagem, reconciliação/resiliência e rollback já possuem evidência mecânica.
- O heartbeat atual do Faro observa capabilities `inventory`, `health`, `telemetry-host`, `portal-host` e `agent-auto-update`; `build` e `runtime` continuam excluídas do perfil Faro.
- O caminho crítico Faro é `10.62.91.5 -> NATS 10.62.92.7:14222 -> cloudiff-control -> PostgreSQL`; Forja e Maurício não participam do heartbeat crítico.
- Releases de agent-skills permanecem imutáveis; o runtime Faro continua na release instalada `cloudiff@0.1.4`, enquanto a skill de projeto usada nesta unidade é `cloudiff@0.1.10`.

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
- Permanecem entradas `pendente`/`preexistente` fora desta unidade no contrato v52; a liberação global do projeto deve selecionar quais delas são release-blocking antes de declarar release final.
- LegacyRetirement continua separado e qualquer retirada destrutiva exige seus próprios gates e autorização final.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `ui-action-map-project-acl`, concluída em `2026-08-27T23:37:00-03:00`; nenhuma zona de exclusão permanece ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.10` — skill raiz; L019 homologado nesta unidade.
- `desenvolvedor-de-software@14` — método PGH para auditoria de tela.
- `github-incremental-reconciliation@7` — reconciliação incremental da skill/catálogo.
- `governanca-ontologica-de-skills@1.0.4` — governança da versão da skill.
- `telemetry-data-visualization@2` — macro global; coletor executável continua indisponível nesta árvore.
- `operational-ui-truth@1` / `navegacao` — prova tela ↔ efeito fora da própria interface.

## Falhas de portão por tipo de entrada
- `ui-compat`: add/remove, owner-block e CSRF negativo passaram, mas o portão sintético de falha Komodo mostrou `project_acl` já commitada com **zero** eventos de reconciliação.
- `teste`: a primeira regressão completa também encontrou teardown excessivo do novo harness removendo entradas preexistentes de `sys.path`; o teste foi isolado para desfazer somente o que ele próprio inseriu.

## Divergências da última reconciliação
### Corrigidas
- `add_acl()`/`remove_acl()` não abortam mais o fluxo depois de persistir a fonte central quando o sync imediato Komodo falha; retornam estado pendente e o wrapper enfileira `project.membership.changed` para convergência durável.
- Add/remove continuam alterando `project_acl`, chamando sync Komodo e enfileirando reconciliação; remoção do dono permanece bloqueada sem DB/sync/fila; CSRF inválido continua sem efeito.
- `cloudiff@0.1.10` registra L019 para preservar o mesmo padrão pós-commit na migração C++23.
- Regressão do Portal: 1027/1027; `validate-repository`, `git diff --check` e `VISUAL_DIFF=NO`: PASS.

### Pendentes de autorização ou capacidade
- A política explícita de quem pode **administrar** ACL além do dono/grupos administrativos não está formalizada nesta unidade; nenhuma regra de autorização nova foi inventada a partir da aparência do botão.
- Runtime de produção da `Visão geral` continua sem promoção; entradas 1515/1516 permanecem `em_curso` até shadow real verde.
- Primeiro salto `172.16.0.1` continua como bloqueio operacional enquanto o plano administrativo não responder.

## Entradas aceitas nesta unidade
- 650 `components/control-plane/srv/cloudif/lib/cloudif_project_acl_module.py` — pós-commit externo reconciliado com fila durável.
- 1522 `portal/tests/test_project_acl_action_effect.py` — add/remove/owner-block/CSRF/sync-failure provados pelo handler final.
- 179 `skills/cloudiff/SKILL.md` — `cloudiff@0.1.10`, L019 homologado.
- 2 `competencias.yaml` — versão da skill raiz reconciliada.
- 9 `estado.md` — snapshot da unidade.
- 10 `manifesto.yaml` — contrato v52 e zona liberada.

## Próxima unidade
- Auditar **Novo projeto → Criar e provisionar projeto** pelo handler final, observando projeto/ACL no SQLite, job durável e evento de reconciliação sem depender do wizard.
- Depois, revisar se há contrato explícito de autorização para administrar ACL e somente então criar portão de negativa por ator.
- Quando o plano de gestão do pfSense voltar, repetir shadow da `Visão geral`; somente shadow verde autoriza promoção.
