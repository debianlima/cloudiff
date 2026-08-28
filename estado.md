# Estado — 2026-08-27 — contrato v48

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
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `ui-action-map-tenant-availability`, concluída; nenhuma zona de exclusão permanece ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.7` — skill raiz; L016 homologado nesta unidade.
- `desenvolvedor-de-software@14` — método PGH para auditoria de tela.
- `github-incremental-reconciliation@7` — reconciliação incremental da skill/catálogo.
- `governanca-ontologica-de-skills@1.0.4` — governança da versão da skill.
- `telemetry-data-visualization@2` — macro global; coletor executável continua indisponível nesta árvore.
- `operational-ui-truth@1` / `navegacao` — prova tela ↔ efeito fora da própria interface.

## Falhas de portão por tipo de entrada
- `ui-compat`: `keepalive` de aluno era visível e parametrizado por `CLOUDIF_MAX_STUDENT_KEEPALIVE_HOURS`, mas o wrapper final devolvia 403 por aplicar guard admin também ao modo temporário.
- `ui-compat`: `start/stop/restart` chegavam ao handler legado com o corpo POST consumido por `do_POST_v21`; `tenant` vazio virava o fallback `projeto` e a autorização falhava.
- `ui-compat`: o primeiro assert de deadline mediu microssegundos contra timestamp persistido em segundos; o teste foi corrigido com tolerância de 1s, sem alteração do produto.

## Divergências da última reconciliação
### Corrigidas
- `do_POST_v21` agora preserva bytes e restaura `rfile`/`Content-Length` quando delega uma ação não tratada, mantendo parâmetros intactos para wrappers anteriores.
- O guard administrativo do wrapper final ficou restrito a `always_on`, `always_on_start` e `always_off`; `keepalive` permanece disponível ao dono visível dentro do limite de horas de aluno.
- Entrada 1518 prova `keepalive`, `start`, `stop`, `always_on_start` e `always_off` contra SQLite temporário + runner Docker fake.
- `cloudiff@0.1.7` registra L016 com entrada, data, portão e regra de compatibilidade para a migração C++23.
- Regressão do Portal: 1015/1015; `validate-repository`, `git diff --check` e `VISUAL_DIFF=NO`: PASS.

### Pendentes de autorização ou capacidade
- Runtime de produção da `Visão geral` continua sem promoção; entradas 1515/1516 permanecem `em_curso` até shadow real verde.
- Primeiro salto `172.16.0.1` segue como bloqueio operacional enquanto o plano administrativo não responder; nenhuma rota paralela foi aberta.

## Entradas aceitas nesta unidade
- 389 `components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py` — forwarding de POST e autorização de disponibilidade reconciliados.
- 1518 `portal/tests/test_tenant_action_effect.py` — efeitos de disponibilidade homologados por SQLite + Docker fake.
- 179 `skills/cloudiff/SKILL.md` — `cloudiff@0.1.7`, L016 homologado.
- 2 `competencias.yaml` — versão da skill raiz reconciliada.
- 9 `estado.md` — snapshot da unidade.
- 10 `manifesto.yaml` — contrato v48 e zona liberada.

## Próxima unidade
- Cruzar os controles mutáveis de **Publicações** contra efeitos observáveis em candidato/fila/runtime, priorizando ações cujo teste atual ainda é textual.
- Em seguida, fazer o mesmo em **Projetos**, especialmente sync/integrate/edit e criação/provisionamento.
- Quando o plano de gestão do pfSense voltar, repetir shadow da correção `Visão geral`; somente shadow verde autoriza promoção.
