# Estado — 2026-08-27 — contrato v45

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a correção desta unidade não altera HTML, CSS, JS visual, textos, botões ou layout.
- O link congelado `Visão geral` (`?tab=resumo`) deve produzir o mesmo painel acadêmico canônico servido na raiz do Portal; o renderer administrativo legado não é contrato visual válido para esse alias.
- Faro é o nó CloudIFF de papel `edge`; seu perfil deseja `portal-host`, mas o cutover do Portal ocorre somente após onboarding Faro e portões de portal shadow.
- O onboarding Faro está aceito: 4 vCPU online, identidade própria, PKI/NATS individual, agent não-root, heartbeat direto para Hospedagem, reconciliação/resiliência e rollback já possuem evidência mecânica.
- O heartbeat atual do Faro observa capabilities `inventory`, `health`, `telemetry-host`, `portal-host` e `agent-auto-update`; `build` e `runtime` continuam excluídas do perfil Faro.
- O caminho crítico Faro é `10.62.91.5 -> NATS 10.62.92.7:14222 -> cloudiff-control -> PostgreSQL`; Forja e Maurício não participam do heartbeat crítico.
- Releases de agent-skills permanecem imutáveis; o runtime Faro continua na release instalada `cloudiff@0.1.4`, enquanto a skill de projeto usada nesta unidade é `cloudiff@0.1.5`.

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
- Permanecem 21 entradas `pendente` e 5 `preexistente` no contrato v45 fora desta unidade; a liberação global do projeto deve selecionar quais delas são release-blocking antes de declarar release final.
- LegacyRetirement continua separado e qualquer retirada destrutiva exige seus próprios gates e autorização final.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `ui-overview-alias-audit`, concluída, sem zona de exclusão ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.5` — skill raiz.
- `desenvolvedor-de-software@14` — método PGH.
- `github-incremental-reconciliation@7` — reconciliação incremental.
- `governanca-ontologica-de-skills@1.0.4` — governança PGH.
- `telemetry-data-visualization@2` — macro global; coletor executável não localizado no repositório desta unidade.
- `navegacao`/Selenium WebDriver 4.46.0 — execução da interface real no WebDev isolado.

## Falhas de portão por tipo de entrada
- `ui-compat`: a navegação real publicou `Visão geral -> ?tab=resumo`, mas o runtime desviava o alias para `render_resumo()` legado enquanto `/cloudiff/portal/` servia o painel acadêmico canônico.
- `webdev`: o link fixo VPN-only devolveu 403 a partir do perfil work porque o tráfego chega ao NPM como `192.168.200.1`; a allowlist continua restrita e não foi ampliada nesta unidade.
- `autenticacao`: a conta AD informada chegou à etapa de senha do Authentik, que respondeu `Invalid password`; nenhuma tentativa adicional foi feita.

## Divergências da última reconciliação
### Corrigidas
- Fonte: `cloudif_portal_v2_coexist.py` não intercepta mais `resumo/visao-geral/visão-geral` no renderer legado; os aliases entram no mesmo `native_home` da raiz.
- Portão: `test_frozen_surfaces_contract.py` agora reprova se o interceptador legado voltar ou se os aliases deixarem o `native_home`.
- Frozen UI 3/3, Portal 1008/1008, `validate-repository`, `git diff --check`: PASS; nenhum arquivo visual alterado.

### Pendentes de autorização ou capacidade
- Runtime de produção ainda contém o adaptador anterior em `/srv/cloudif/lib`; não há mecanismo versionado localizado nesta árvore para rollout/rollback isolado dessa biblioteca. Não foi feito overwrite root manual.
- O acesso WebDev por URL fixa no perfil work continua divergente da allowlist declarada; requer reconciliação de rota/origem, sem abrir exposição pública.

## Entradas aceitas nesta unidade
- 649 `components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py` — alias da Visão geral reconciliado com o `native_home` canônico.
- 1196 `portal/tests/test_frozen_surfaces_contract.py` — regressão capturada mecanicamente.
- 9 `estado.md` — snapshot da auditoria da interface.
- 10 `manifesto.yaml` — trabalho compartilhado encerrado sem zona ativa.

## Próxima unidade
- Criar/identificar mecanismo versionado de rollout/rollback para a biblioteca Portal v2 e aplicar a correção em shadow antes do runtime ativo.
- Após rollout, executar novamente raiz versus `?tab=resumo` por canal HTTP independente e Selenium, exigindo equivalência do painel canônico.
- Reconciliar o caminho VPN do WebDev sem ampliar exposição pública.
