# Estado — 2026-08-27 — contrato v49

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a correção desta unidade não altera HTML, CSS, JS visual, textos, botões ou layout.
- O link congelado `Visão geral` (`?tab=resumo`) deve produzir o mesmo painel acadêmico canônico servido na raiz do Portal; o renderer administrativo legado não é contrato visual válido para esse alias.
- Faro é o nó CloudIFF de papel `edge`; seu perfil deseja `portal-host`, mas o cutover do Portal ocorre somente após onboarding Faro e portões de portal shadow.
- O onboarding Faro está aceito: 4 vCPU online, identidade própria, PKI/NATS individual, agent não-root, heartbeat direto para Hospedagem, reconciliação/resiliência e rollback já possuem evidência mecânica.
- O heartbeat atual do Faro observa capabilities `inventory`, `health`, `telemetry-host`, `portal-host` e `agent-auto-update`; `build` e `runtime` continuam excluídas do perfil Faro.
- O caminho crítico Faro é `10.62.91.5 -> NATS 10.62.92.7:14222 -> cloudiff-control -> PostgreSQL`; Forja e Maurício não participam do heartbeat crítico.
- Releases de agent-skills permanecem imutáveis; o runtime Faro continua na release instalada `cloudiff@0.1.4`, enquanto a skill de projeto usada nesta unidade é `cloudiff@0.1.7`.

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
- Permanecem entradas `pendente`/`preexistente` fora desta unidade no contrato v46 fora desta unidade; a liberação global do projeto deve selecionar quais delas são release-blocking antes de declarar release final.
- LegacyRetirement continua separado e qualquer retirada destrutiva exige seus próprios gates e autorização final.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `ui-action-map-publication-alias`, concluída; nenhuma zona de exclusão permanece ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.7` — skill raiz, recarregada do branch auditável remoto antes da unidade.
- `desenvolvedor-de-software@14` — método PGH para auditoria de tela.
- `github-incremental-reconciliation@7` — reconciliação incremental de branch/estrutura.
- `telemetry-data-visualization@2` — macro global; coletor executável continua indisponível nesta árvore.
- `operational-ui-truth@1` / `navegacao` — prova tela ↔ efeito fora da própria interface.

## Falhas de portão por tipo de entrada
- Nenhuma divergência funcional encontrada em `set_alias`: o handler final preserva CSRF, autorização do dono, atualização do publisher, persistência SQLite e auditoria.
- O portão negativo comprovou que ausência de CSRF retorna 403 sem linha de alias nem chamada ao publisher.

## Divergências da última reconciliação
### Corrigidas
- Entrada 1519 adiciona prova executável do caminho **Salvar endereço**: formulário/handler → `project_publication_aliases` → publisher `/alias` → `action_log`.
- Com publicação ativa P42/d3, o payload observado no publisher preserva `public_number=42`, `deploy_number=3` e o alias escolhido.
- Regressão do Portal: 1017/1017; `validate-repository`, `git diff --check` e `VISUAL_DIFF=NO`: PASS.

### Pendentes de autorização ou capacidade
- Runtime de produção da `Visão geral` continua sem promoção; entradas 1515/1516 permanecem `em_curso` até shadow real verde.
- Primeiro salto `172.16.0.1` segue como bloqueio operacional enquanto o plano administrativo não responder.

## Entradas aceitas nesta unidade
- 1519 `portal/tests/test_publication_alias_action_effect.py` — efeito do alias homologado por SQLite + publisher + log e negativo CSRF.
- 9 `estado.md` — snapshot da unidade.
- 10 `manifesto.yaml` — contrato v49 e zona liberada.

## Próxima unidade
- Auditar o wizard **Gerenciar publicação** em W/H/P, começando por `homologation/enqueue` e produção com aprovação, observando fila/candidato sem depender do modal.
- Depois, cruzar ações de Projetos (`check`, `sync`, `integrate`, `edit_save`) contra DB/comandos reais simulados.
- Quando o plano de gestão do pfSense voltar, repetir shadow da `Visão geral`; somente shadow verde autoriza promoção.
