# Estado — 2026-08-27 — contrato v50

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a correção desta unidade não altera HTML, CSS, JS visual, textos, botões ou layout.
- O link congelado `Visão geral` (`?tab=resumo`) deve produzir o mesmo painel acadêmico canônico servido na raiz do Portal; o renderer administrativo legado não é contrato visual válido para esse alias.
- Faro é o nó CloudIFF de papel `edge`; seu perfil deseja `portal-host`, mas o cutover do Portal ocorre somente após onboarding Faro e portões de portal shadow.
- O onboarding Faro está aceito: 4 vCPU online, identidade própria, PKI/NATS individual, agent não-root, heartbeat direto para Hospedagem, reconciliação/resiliência e rollback já possuem evidência mecânica.
- O heartbeat atual do Faro observa capabilities `inventory`, `health`, `telemetry-host`, `portal-host` e `agent-auto-update`; `build` e `runtime` continuam excluídas do perfil Faro.
- O caminho crítico Faro é `10.62.91.5 -> NATS 10.62.92.7:14222 -> cloudiff-control -> PostgreSQL`; Forja e Maurício não participam do heartbeat crítico.
- Releases de agent-skills permanecem imutáveis; o runtime Faro continua na release instalada `cloudiff@0.1.4`, enquanto a skill de projeto usada nesta unidade é `cloudiff@0.1.8`.

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
- Permanecem entradas `pendente`/`preexistente` fora desta unidade no contrato v50; a liberação global do projeto deve selecionar quais delas são release-blocking antes de declarar release final.
- LegacyRetirement continua separado e qualquer retirada destrutiva exige seus próprios gates e autorização final.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `ui-action-map-release-flow-http`, concluída; nenhuma zona de exclusão permanece ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.8` — skill raiz; L017 homologado nesta unidade.
- `desenvolvedor-de-software@14` — método PGH para auditoria de tela.
- `github-incremental-reconciliation@7` — reconciliação incremental da skill/catálogo.
- `governanca-ontologica-de-skills@1.0.4` — governança da versão da skill.
- `telemetry-data-visualization@2` — macro global; coletor executável continua indisponível nesta árvore.
- `operational-ui-truth@1` / `navegacao` — prova tela ↔ efeito fora da própria interface.

## Falhas de portão por tipo de entrada
- `ui-compat`: o primeiro harness HTTP precisou de `do_GET` mínimo porque o adaptador v2 envolve a classe inteira; correção restrita ao teste.
- `backend-integracao`: `production/enqueue` retornava 503 `NameError` antes de validar aprovação/digest porque `cloudif_portal_publications.py` usava `hmac.compare_digest` sem importar `hmac`.
- `backend-integracao`: digest incorreto também virava 503 em vez de 403, provando que o guard textual não era um guard executável.

## Divergências da última reconciliação
### Corrigidas
- As duas projeções versionadas de `cloudif_portal_publications.py` importam `hmac` e permanecem byte-idênticas.
- Entrada 1520 executa `homologation/enqueue` pelo HTTP final: cria uma única `publication_jobs` H1 e a repetição reutiliza o job existente.
- CSRF ausente retorna 403 sem criar fila.
- `production/enqueue` aprovado vincula candidato, `approval_id`, `activation_digest` e P na fila; digest divergente retorna 403 sem fila e preserva a ativação aprovada.
- `cloudiff@0.1.8` registra L017 para impedir que guard presente no código seja aceito sem executar a rota protegida.
- Regressão do Portal: 1021/1021; `validate-repository`, `git diff --check` e `VISUAL_DIFF=NO`: PASS.

### Pendentes de autorização ou capacidade
- Runtime de produção da `Visão geral` continua sem promoção; entradas 1515/1516 permanecem `em_curso` até shadow real verde.
- Primeiro salto `172.16.0.1` segue como bloqueio operacional enquanto o plano administrativo não responder; nenhuma rota paralela foi aberta.

## Entradas aceitas nesta unidade
- 393 `components/control-plane/current-apps/portal-current/cloudif_portal_publications.py` — guard de aprovação/digest executável após import de `hmac`.
- 648 `components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py` — projeção reconciliada e byte-idêntica.
- 1520 `portal/tests/test_release_flow_action_effect.py` — W/H/P homologado por HTTP final + SQLite, incluindo negativos CSRF/digest.
- 179 `skills/cloudiff/SKILL.md` — `cloudiff@0.1.8`, L017 homologado.
- 2 `competencias.yaml` — versão da skill raiz reconciliada.
- 9 `estado.md` — snapshot desta unidade.
- 10 `manifesto.yaml` — contrato v50 e zona liberada.

## Próxima unidade
- Auditar ações mutáveis de **Projetos** (`check`, `sync`, `integrate`, `edit_save`) pelo handler final e efeito em DB/comandos, sem depender de mensagens da tela.
- Depois, completar W/H/P com o pedido de aprovação de Produção e o worker, mantendo a prova de que H e P usam o mesmo artefato.
- Quando o plano de gestão do pfSense voltar, repetir shadow da `Visão geral`; somente shadow verde autoriza promoção.
