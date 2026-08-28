# Estado — 2026-08-27 — contrato v47

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a correção desta unidade não altera HTML, CSS, JS visual, textos, botões ou layout.
- O link congelado `Visão geral` (`?tab=resumo`) deve produzir o mesmo painel acadêmico canônico servido na raiz do Portal; o renderer administrativo legado não é contrato visual válido para esse alias.
- Faro é o nó CloudIFF de papel `edge`; seu perfil deseja `portal-host`, mas o cutover do Portal ocorre somente após onboarding Faro e portões de portal shadow.
- O onboarding Faro está aceito: 4 vCPU online, identidade própria, PKI/NATS individual, agent não-root, heartbeat direto para Hospedagem, reconciliação/resiliência e rollback já possuem evidência mecânica.
- O heartbeat atual do Faro observa capabilities `inventory`, `health`, `telemetry-host`, `portal-host` e `agent-auto-update`; `build` e `runtime` continuam excluídas do perfil Faro.
- O caminho crítico Faro é `10.62.91.5 -> NATS 10.62.92.7:14222 -> cloudiff-control -> PostgreSQL`; Forja e Maurício não participam do heartbeat crítico.
- Releases de agent-skills permanecem imutáveis; o runtime Faro continua na release instalada `cloudiff@0.1.4`, enquanto a skill de projeto usada nesta unidade é `cloudiff@0.1.6`.

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
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `ui-action-map-tenant-acl`, concluída; nenhuma zona de exclusão permanece ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.6` — skill raiz, conferida no remoto antes da unidade.
- `desenvolvedor-de-software@14` — método PGH para auditoria de tela.
- `github-incremental-reconciliation@7` — reconciliação de branch/estrutura.
- `telemetry-data-visualization@2` — macro global; coletor executável continua indisponível nesta árvore.
- `operational-ui-truth@1` / `navegacao` — prova tela ↔ efeito fora da própria interface.

## Falhas de portão por tipo de entrada
- `ui-compat`: o primeiro portão de ACL não chegou à ação porque o módulo-base inicializa telemetria em `/var/lib/cloudif/access-ingest`; o teste foi isolado com `CLOUDIF_ACCESS_INGEST_DB` temporário, sem alterar produção.
- `ui-compat`: o segundo portão precisou incluir `portal-current` no `sys.path` do teste para carregar módulos irmãos; novamente, correção restrita ao ambiente de teste.
- Nenhuma divergência funcional foi encontrada em `tenant_acl`: add/remove/owner-block bateram com o efeito declarado.

## Divergências da última reconciliação
### Corrigidas
- Entrada 1517 agora executa o handler final de `/action/tenant_acl` com CSRF/origin válidos contra SQLite temporário e provedor/fila controlados.
- `Adicionar`: linha aparece em `tenant_acl` e evento `tenant.membership.changed` com `operation=add` é observado.
- `Remover`: linha desaparece e evento com `operation=remove` é observado.
- Remoção do proprietário: HTTP 409, linha preservada e fila permanece vazia.
- Regressão do Portal: 1011/1011; `validate-repository`, `git diff --check` e `VISUAL_DIFF=NO`: PASS.

### Pendentes de autorização ou capacidade
- Runtime de produção da `Visão geral` continua sem promoção; entradas 1515/1516 permanecem `em_curso` até shadow real verde.
- Primeiro salto `172.16.0.1` permanece bloqueio operacional para nova homologação remota enquanto o plano administrativo não voltar.

## Entradas aceitas nesta unidade
- 1517 `portal/tests/test_tenant_acl_action_effect.py` — ACL de banco homologada por SQLite + fila independentes, incluindo owner-block.
- 9 `estado.md` — snapshot da auditoria ACL.
- 10 `manifesto.yaml` — contrato v47 e zona liberada.

## Próxima unidade
- Auditar `tenant_action` de Bancos: **Iniciar temporariamente**, **Ativar sempre ligado** e **desligamento automático**, observando política SQLite e execução Docker fake separadamente.
- Depois, cruzar Publicações e Projetos contra os mesmos critérios de efeito independente.
- Quando o plano de gestão do pfSense voltar, repetir shadow da correção `Visão geral` antes de qualquer promoção.
