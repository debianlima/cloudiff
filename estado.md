# Estado — 2026-08-28 — contrato v57

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a correção desta unidade não altera HTML, CSS, JS visual, textos, botões ou layout.
- O link congelado `Visão geral` (`?tab=resumo`) deve produzir o mesmo painel acadêmico canônico servido na raiz do Portal; o renderer administrativo legado não é contrato visual válido para esse alias.
- A promoção produtiva da correção `Visão geral` está homologada: live hash `1ae42e1e...`, `current` no candidato, `previous` no baseline `4407bd7c...`, raiz/alias/navigation equivalentes e verificador residente `errors=0`.
- Faro é o nó CloudIFF de papel `edge`; seu perfil deseja `portal-host`, mas o cutover do Portal ocorre somente após onboarding Faro e portões de portal shadow.
- O onboarding Faro está aceito: 4 vCPU online, identidade própria, PKI/NATS individual, agent não-root, heartbeat direto para Hospedagem, reconciliação/resiliência e rollback já possuem evidência mecânica.
- O heartbeat atual do Faro observa capabilities `inventory`, `health`, `telemetry-host`, `portal-host` e `agent-auto-update`; `build` e `runtime` continuam excluídas do perfil Faro.
- O caminho crítico Faro é `10.62.91.5 -> NATS 10.62.92.7:14222 -> cloudiff-control -> PostgreSQL`; Forja e Maurício não participam do heartbeat crítico.
- Releases de agent-skills permanecem imutáveis; o runtime Faro continua na release instalada `cloudiff@0.1.4`, enquanto a skill de projeto usada nesta unidade é `cloudiff@0.1.15`.

## Decisões superadas
- Salto obrigatório via `172.16.0.1` para acessar máquinas do laboratório — superado em 28/08/2026 pela nova orientação da TI comunicada pelo operador; acesso operacional passa a ser direto pelo conector Labiff, mantendo pfSense/MikroTik apenas como equipamentos de rede quando necessário.
- Faro bloqueado por `2/4 vCPU` — superado em 26/08/2026 após a TI ampliar a VM e o SO observar CPUs `0-3`.
- `portal-host` apenas desejada/não observada — superado pelo heartbeat PostgreSQL atual, que já anuncia `portal-host`; isso não equivale a cutover do Portal.
- Confiar apenas na árvore de uma release de skills já existente como prova do artefato recebido — superado na v45 pelo gate do TAR recebido.

## Decisões humanas pendentes
- Nenhuma decisão humana adicional para aceitar o nó Faro.
- Cutover definitivo do Portal para Faro permanece uma unidade posterior e deve respeitar os portões de portal shadow/FrozenPortalInterface; não foi executado implicitamente nesta unidade.

## Decisões fechadas nesta emenda
- O caminho consumido pelo Portal `Hospedagem -> cloudif-publisher.internal -> NpmPublisherProvider C++` tem paridade observada para health, autenticação negativa e rejeição de stage inválido sem mutação de estado/Nginx.
- A release live do publisher é `0.10.0-shadow`; o source atual do branch declara `0.36.0-shadow`. Sem commit de procedência da v10, **não** se declara que o source atual está implantado.
- `cloudiff-control` C++ assina somente `cloudiff.v2.node.observed`; portanto reconciliação de projetos/eventos `project.created` e `project.membership.changed` **não** está declarada como migrada.

## Pendências técnicas não humanas
- NPM/Maurício (`10.62.91.3`) reprova o verificador por filesystem `/` em 91% (`errors=1`); nenhum novo build/deploy C++ deve ocorrer nesse host até reconciliar capacidade.
- A procedência exata da release live `/opt/cloudiff-v2/releases/20260820-v10-npm-publisher-acme` não é recuperável do histórico Git disponível; `live_source_commit=NAO DECLARADO` permanece explícito.
- Reconciliação C++ de projeto/publicação ainda não possui consumidor equivalente aos eventos duráveis do Portal; o `cloudiff-control` atual é restrito a observação de nó.
- O host Faro mantém `fwupd-refresh.service` falho por indisponibilidade de egress; o verificador residente já tratava isso como warning não bloqueante do runtime CloudIFF/NATS.
- Permanecem entradas `pendente`/`preexistente` fora desta unidade no contrato v57; LegacyRetirement continua separado e destrutivo somente com gates próprios.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `cpp23-publication-reconciliation-parity`, concluída em `2026-08-28T01:57:53-03:00`; nenhuma zona de exclusão permanece ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.15` — skill raiz; L023 e L024 homologados nesta unidade.
- `desenvolvedor-de-software@14` — método PGH.
- `github-incremental-reconciliation@7` — reconciliação incremental de skill/catálogo.
- `governanca-ontologica-de-skills@1.0.4` — governança da versão da skill.
- `telemetry-data-visualization@2` — macro global; coletor executável indisponível, medida classificada como `indisponivel`.
- `operational-ui-truth@1` / `platform-engineering` — paridade observada no caminho real Portal→provider e capacity gate do host.

## Falhas de portão por tipo de entrada
- `infraestrutura`: verificador do NPM retorna `errors=1` porque filesystem `/` está em 91%; bloqueia novo deploy no host, não a auditoria read-only do runtime já ativo.
- `procedencia`: binário live reporta `0.10.0-shadow`, enquanto o branch auditado reporta `0.36.0-shadow`; o histórico reconciliado não liga a release v10 a um commit fonte específico.
- `reconciliacao`: nenhum erro funcional foi atribuído ao publisher; o limite encontrado é de escopo — `cloudiff-control` atual consome somente observação de nó, não eventos de projeto.
- `skill-projeto`: o gate da entrada 182 fixava `cloudiff@0.1.5` e depois comparava a evidência histórica v40 com `/srv/cloudif/agent-skills/current`; ambos os pressupostos envelheceram e reprovaram uma evolução válida.

## Divergências da última reconciliação
### Corrigidas
- Entrada 1527 registra evidência sem segredo do ingress real: Hospedagem `10.62.92.7` → `10.62.91.3:80` com `Host: cloudif-publisher.internal`, health 200 e token inválido 403.
- Shadow v8 (`127.0.0.1:18260`) e live v10 (`10.62.91.3:18160`) retornaram 422 `ValueError/invalid_stage` com token válido, mantendo `state.json` e configuração Nginx com hashes inalterados.
- Entrada 1528 cruza as oito rotas do contrato com o provider C++ e os consumidores do Portal e impede afirmar que `0.36.0` está live ou que reconciliação de projetos já migrou.
- `cloudiff@0.1.15` registra L023 e L024: presença de C++/nome de serviço não equivale a substituição homologada sem identidade/procedência/cobertura; o gate da skill compara versão dinamicamente e preserva procedência histórica sem ler o ponteiro `current`.
- Entrada 182 agora valida `SKILL.md` ↔ `competencias.yaml` e os seis refs v40 por `repository/commit/path/versao_fixada/sha256`, sem pin histórico da versão raiz.
- Nenhum HTML/CSS/JS visual foi alterado; `FrozenPortalInterface` permanece intacta.

### Pendentes de autorização ou capacidade
- Resolver ocupação do filesystem do NPM antes de qualquer atualização do publisher C++.
- Recuperar procedência da release v10 se existir fora do histórico reconciliado; enquanto isso o campo permanece `NAO DECLARADO`.
- O `main` do Cloudiff continua separado do branch auditável; nenhum merge foi inferido.

## Entradas aceitas nesta unidade
- 1527 `docs/reconciliation/npm-publisher-runtime-parity-v57.json` — evidência runtime live/shadow/ingress sem segredo e limites explícitos.
- 1528 `tests/test_npm_publisher_runtime_parity_evidence.py` — Portal/contrato/provider/evidência cruzados mecanicamente.
- 182 `tests/test_cloudiff_project_skill.py` — versão raiz dinâmica e procedência v40 sem dependência do `current` mutável.
- 179 `skills/cloudiff/SKILL.md` — `cloudiff@0.1.15`, L023/L024 homologados.
- 2 `competencias.yaml` — skill raiz reconciliada em `0.1.15`.
- 9 `estado.md` — snapshot v57.
- 10 `manifesto.yaml` — contrato v57 e zona liberada.

## Próxima unidade
- Auditar a paridade do `RuntimeExecutor` C++ para os perfis Homologação/Produção consumidos pelo fluxo W/H/P, sem executar benchmark/simulação fora do Samba4.
- Em paralelo, tratar reconciliação de projetos C++ apenas quando o outro fluxo publicar um consumidor explícito dos eventos duráveis do Portal; não inventar esse vínculo no `cloudiff-control` atual.
