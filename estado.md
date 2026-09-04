# Estado — 2026-09-04 — contrato v49

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a U15 alterou somente a superfície **Aprovações** explicitamente autorizada pelo operador: estado ativo no tema escuro e histórico sob demanda.
- `teste-sofa` permanece projeto descartável de QA do owner `iff1742962`, tenant `iff1742962-testesofa`, runtime `running`, `healthy=true`, `issues=[]` e terminal OK.
- P2 continua vinculada ao candidato H2 e exige duas aprovações humanas distintas admin/professor, ambas diferentes do solicitante.
- A autorização P2 mais recente `apr_dd84dba1cc5f49219d67` expirou sem aprovadores; quando os aprovadores estiverem presentes, o gate deve ser renovado pelo endpoint oficial antes de continuar.
- A navegação principal de Aprovações permanece como homologada na v47; a U15 não adicionou novas rotas nem itens de menu.
- A skill de projeto vigente passa a `cloudiff@0.1.11`.

## Decisões superadas
- Usar `--accent`/`--accent-soft` no item ativo da navegação contextual de Aprovações — superado porque esses tokens não existem no escopo global do shell v2 e o tema escuro caía para texto claro sem fundo.
- Renderizar todo o histórico de aprovações diretamente antes de **Sempre permitir** — superado por carregamento sob demanda em diálogo nativo.

## Decisões humanas pendentes
- H001 P2 do `teste-sofa`: não existe autorização ativa neste momento; a última expirou. Para retomar, renovar P2 e obter duas decisões humanas distintas admin/professor, sem usar o solicitante como aprovador.

## Decisões fechadas nesta emenda
- O ajuste de cor foi escopado a `.tab-aprovacoes`; demais tabs/contextos não foram redesenhados.
- O item contextual ativo usa `--iff-wash` no fundo e `--iff-dark` no texto, preservando tokens canônicos nos temas claro e escuro.
- Estados `pending`, `pending_second` e `approved` permanecem no fluxo principal; `expired`, `consumed`, `rejected` e `cancelled` vão para **Carregar histórico**.
- **Carregar histórico (N)** abre um `<dialog>` nativo e o fecha sem navegação nem request adicional.
- `versao_contrato` avançou para 49 e a entrada 1517 fixa o comportamento de tema/histórico.

## Pendências técnicas não humanas
- Nenhuma pendência técnica permanece na superfície Aprovações tratada pela U15.
- A divergência de U14 em **Gerenciar permissões** do Teste Sofá — drawer vazio no navegador — permanece fora do escopo desta correção e deve ser tratada em unidade própria.
- Após H001: executar P2, validar artefato/HTTPS/terminal/stable URL e exercitar rollback real para P1.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — vazio após o fechamento da U15; nenhuma zona de exclusão permanece reservada.

## Competências ativas nesta unidade
- `cloudiff@0.1.11` — skill raiz, atualizada com L022/L023 após homologação viva.
- `desenvolvedor-de-software@15` — método PGH vigente.
- `github-incremental-reconciliation@7` — reconciliação incremental.
- `governanca-ontologica-de-skills@1.0.5` — política vigente.
- `telemetry-data-visualization@2` — macro global obrigatória.

## Falhas de portão por tipo de entrada
- `interface/tema`: item contextual ativo de Aprovações em dark resolvia para texto quase branco e fundo transparente porque os tokens usados estavam fora de escopo.
- `interface/ergonomia`: 18 registros históricos ficavam expandidos antes de **Sempre permitir**, prejudicando a leitura das políticas persistentes.

## Divergências da última reconciliação
### Corrigidas
- `portal/design/components.css`: override dark-safe limitado a `.tab-aprovacoes` com tokens IFF globais.
- `cloudif_approval_panel.py`: histórico terminal removido do fluxo principal e exposto em `<dialog>` sob demanda.
- Deploy ativo U15 troca apenas o painel de aprovações e o CSS do shell, preservando os releases vivos anteriores como base e rollback.
- Navegação viva em Chromium: Projetos → Aprovações manteve `data-theme=dark`; item contextual ativo ficou verde (`rgb(149, 223, 163)`) sobre verde escuro (`rgb(23, 53, 31)`).
- O browser encontrou exatamente um botão `Carregar histórico (18)`; **Sempre permitir** ficou visível imediatamente abaixo do resumo; o modal abriu com 18 registros e fechou normalmente.
- Console errors 0, page errors 0, failed requests 0 durante o reteste.

### Pendentes fora do escopo
- U14: `Gerenciar permissões` do projeto abriu um drawer sem conteúdo; não foi alterado na U15 por solicitação de limitar a mudança ao menu/painel de Aprovações.
- H001: P2 precisa ser renovada e decidida por dois humanos autorizados.

## Entradas aceitas nesta unidade
- 1517 — regressão do tema escuro e histórico sob demanda de Aprovações.
- 1352 — navegação contextual reutilizada sem nova rota; correção visual escopada à tab Aprovações.
- 392 — painel de Aprovações com histórico em diálogo nativo.
- `portal/FROZEN_SURFACES.md` — emenda visual explicitamente autorizada.
- `skills/cloudiff/SKILL.md` — L022/L023 e versão 0.1.11.
- `competencias.yaml` — skill de projeto 0.1.11.

## Portões da unidade
- `U15_TESTS=PASS`: 27/27 contratos de tema, histórico, aprovação, navegação e superfície congelada.
- `LIVE_DARK_APPROVALS_HISTORY=PASS`: clique real Projetos→Aprovações em Chromium dark, tokens corretos, diálogo funcional e **Sempre permitir** desobstruído.
- `PY_COMPILE=PASS`, `DIFF_CHECK=PASS`, `SECRET_SCAN=PASS`.
- `DELTA_INVENTORY=PASS`, `LEARNING_PRESERVED=PASS`: catálogo permaneceu em `9b951d0d2f68a3ead190741fd5e8b4d6cc8e0a84`, sem delta nas skills consumidas.

## Próxima unidade
- Tratar separadamente o drawer vazio de **Gerenciar permissões**; quando houver dois aprovadores humanos disponíveis, renovar P2 e concluir publicação + smoke + rollback.
