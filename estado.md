# Estado — 2026-08-27 — contrato v46

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
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `ui-action-map-backup-remote-config`, concluída; nenhuma zona de exclusão permanece ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.6` — skill raiz; L015 homologado nesta unidade.
- `desenvolvedor-de-software@14` — método PGH.
- `github-incremental-reconciliation@7` — reconciliação incremental para a atualização da skill/catálogo.
- `governanca-ontologica-de-skills@1.0.4` — governança da versão da skill.
- `telemetry-data-visualization@2` — macro global; coletor executável continua indisponível nesta árvore.
- `operational-ui-truth@1` / `navegacao` — mapa tela ↔ efeito com canal independente.

## Falhas de portão por tipo de entrada
- `ui-compat`: o controle congelado **“Testar e salvar”** do backup remoto possuía teste por presença de strings, sem executar nem observar o artefato persistido; o primeiro teste executável reprovou como esperado antes da correção.
- `ui-compat`: a navegação real publicou `Visão geral -> ?tab=resumo`, mas o runtime produtivo ainda contém o adaptador anterior; a correção permanece versionada e não promovida enquanto o shadow real não passar.
- `webdev`: o link fixo VPN-only devolveu 403 a partir do perfil work porque o tráfego chega ao NPM por origem não coberta pela allowlist; nenhuma exposição foi ampliada.
- `autenticacao`: a conta AD informada foi recusada pelo Authentik na etapa de senha; não houve tentativa repetida.

## Divergências da última reconciliação
### Corrigidas
- `backup_remote_config`: leitura e escrita agora usam a mesma fonte canônica `BACKUP_REMOTE_ENV`.
- O efeito de **“Testar e salvar”** é provado por bytes antes/depois, conteúdo exato, modo `0600`, replace atômico e ausência de temporário residual; toast/string não contam como evidência.
- `cloudiff@0.1.6` registra L015 com entrada, data, portão, plataforma e pressupostos.
- Regressão do Portal: 1009/1009; `validate-repository`, `git diff --check` e `VISUAL_DIFF=NO`: PASS.

### Pendentes de autorização ou capacidade
- Runtime de produção ainda contém o adaptador anterior da `Visão geral`; entradas 1515/1516 permanecem `em_curso` até novo shadow real verde. Não houve promoção ou overwrite root.
- Primeiro salto `172.16.0.1` segue com plano administrativo indisponível nas últimas sondagens; isso impede nova homologação na Hospedagem sem justificar bypass da segmentação.
- O acesso WebDev por URL fixa no perfil work continua pendente de reconciliação de rota/origem, sem ampliar exposição pública.

## Entradas aceitas nesta unidade
- 649 `components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py` — persistência do backup remoto reconciliada com `BACKUP_REMOTE_ENV` e replace atômico.
- 1178 `portal/tests/test_backup_remote_global_config.py` — efeito do controle provado por artefato independente.
- 179 `skills/cloudiff/SKILL.md` — `cloudiff@0.1.6`, L015 homologado.
- 2 `competencias.yaml` — versão da skill raiz reconciliada.
- 9 `estado.md` — snapshot desta unidade.
- 10 `manifesto.yaml` — entradas aceitas e zona liberada.

## Próxima unidade
- Auditar ações mutáveis de **Bancos/tenants**, começando por adicionar/remover ACL e start/stop, exigindo efeito observado em arquivo/DB/processo/rota fora da interface.
- Em seguida, aplicar o mesmo cruzamento a Publicações e Projetos, priorizando controles cujo teste atual só inspeciona strings/HTML.
- Quando o plano de gestão do pfSense voltar, repetir `plan -> prepare -> shadow` da Visão geral; somente shadow verde autoriza promoção.
