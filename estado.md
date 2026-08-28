# Estado — 2026-08-28 — contrato v56

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a correção desta unidade não altera HTML, CSS, JS visual, textos, botões ou layout.
- O link congelado `Visão geral` (`?tab=resumo`) deve produzir o mesmo painel acadêmico canônico servido na raiz do Portal; o renderer administrativo legado não é contrato visual válido para esse alias.
- A promoção produtiva da correção `Visão geral` está homologada: live hash `1ae42e1e...`, `current` no candidato, `previous` no baseline `4407bd7c...`, raiz/alias/navigation equivalentes e verificador residente `errors=0`.
- Faro é o nó CloudIFF de papel `edge`; seu perfil deseja `portal-host`, mas o cutover do Portal ocorre somente após onboarding Faro e portões de portal shadow.
- O onboarding Faro está aceito: 4 vCPU online, identidade própria, PKI/NATS individual, agent não-root, heartbeat direto para Hospedagem, reconciliação/resiliência e rollback já possuem evidência mecânica.
- O heartbeat atual do Faro observa capabilities `inventory`, `health`, `telemetry-host`, `portal-host` e `agent-auto-update`; `build` e `runtime` continuam excluídas do perfil Faro.
- O caminho crítico Faro é `10.62.91.5 -> NATS 10.62.92.7:14222 -> cloudiff-control -> PostgreSQL`; Forja e Maurício não participam do heartbeat crítico.
- Releases de agent-skills permanecem imutáveis; o runtime Faro continua na release instalada `cloudiff@0.1.4`, enquanto a skill de projeto usada nesta unidade é `cloudiff@0.1.13`.

## Decisões superadas
- Salto obrigatório via `172.16.0.1` para acessar máquinas do laboratório — superado em 28/08/2026 pela nova orientação da TI comunicada pelo operador; acesso operacional passa a ser direto pelo conector Labiff, mantendo pfSense/MikroTik apenas como equipamentos de rede quando necessário.
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
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `portal-v2-rollout-smoke-propagation`, concluída; nenhuma zona de exclusão permanece ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.13` — skill raiz; L022 homologado nesta unidade.
- `desenvolvedor-de-software@14` — método PGH.
- `github-incremental-reconciliation@7` — reconciliação incremental da skill/catálogo.
- `governanca-ontologica-de-skills@1.0.4` — governança da versão da skill.
- `telemetry-data-visualization@2` — macro global; coletor executável indisponível, medida classificada como `indisponivel`.
- `operational-ui-truth@1` / `release-it` — prova de efeito live por canal independente + rollback.

## Falhas de portão por tipo de entrada
- `deploy`: após shadow verde e troca live, `smoke_live()` imprimiu PASS falso quando `curl` falhou na janela de restart; Bash suprimiu a semântica esperada de `set -e` por a função estar em contexto condicional.
- `deploy`: `trap RETURN` de `smoke_url()` sobreviveu ao retorno antecipado e caiu depois com `root_page: unbound variable`, produzindo `exit 1` mesmo com o Portal já saudável.

## Divergências da última reconciliação
### Corrigidas
- Shadow real passou em `19080` com o candidato `1ae42e1e7d668474...`; promoção colocou o mesmo hash no live, `current` no candidato e `previous` no baseline `4407bd7c216ad722...`.
- Smoke independente pós-restart provou raiz e `?tab=resumo` com os três marcadores acadêmicos e `/api/navigation` com `secrets_exposed=false`, `unique_routes_required=true` e policy canônica.
- `smoke_url()` não usa mais `trap RETURN`; limpa temporários explicitamente e devolve `rc` controlado. `smoke_live()` não imprime PASS se o smoke falhar.
- Portão remoto de falha em 19999: rc não-zero, sem PASS falso e sem `unbound variable`; smoke real em 18094: PASS.
- Verificador residente da Hospedagem após promoção: `errors=0`, warning já declarado.
- `cloudiff@0.1.13` registra L022; `VISUAL_DIFF=NO` permanece obrigatório.

### Pendentes de autorização ou capacidade
- O `main` do Cloudiff permanece separado do branch auditável; nenhum merge foi inferido.
- A migração dos agentes para C++23 continua sob outro fluxo; esta auditoria deve provar paridade funcional sem alterar `FrozenPortalInterface`.

## Entradas aceitas nesta unidade
- 1515 `deploy/apply_portal_v2_lib_release.sh` — shadow, promoção, rollback metadata e propagação de falha do smoke homologados em ambiente real.
- 1516 `tests/test_portal_v2_lib_release.py` — regressão do smoke em contexto condicional adicionada e verde.
- 179 `skills/cloudiff/SKILL.md` — `cloudiff@0.1.13`, L022 homologado.
- 2 `competencias.yaml` — versão da skill raiz reconciliada.
- 9 `estado.md` — snapshot pós-promoção.
- 10 `manifesto.yaml` — entradas 1515/1516 aceitas e zona liberada.

## Próxima unidade
- Auditar a paridade dos agentes já migrados para C++23 contra os contratos consumidos pelas superfícies congeladas, começando por publicação/reconciliação.
- Não executar benchmark/simulação fora da máquina Samba4 autorizada; testes funcionais determinísticos podem rodar nas máquinas de desenvolvimento homologadas.
