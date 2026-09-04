# Estado — 2026-09-04 — contrato v50

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a U16 alterou somente a coerência visual das rotas já existentes **Código** e **Produção** dentro da navegação contextual.
- `teste-sofa` permanece projeto descartável de QA do owner `iff1742962`, tenant `iff1742962-testesofa`; o último smoke conhecido mantém runtime saudável e terminal operacional.
- P2 continua dependente de duas aprovações humanas distintas admin/professor, ambas diferentes do solicitante; a autorização anterior expirou e deverá ser renovada quando houver os aprovadores.
- A negativa de acesso a **Produção** permanece HTTP 403; a U16 só fez o 403 usar o shell canônico.
- A skill de projeto vigente passa a `cloudiff@0.1.12`.

## Decisões superadas
- Considerar suficiente corrigir apenas o fundo do shell da aba **Código** — superado: os cards legacy carregavam `#fff` próprio e permaneciam brancos no dark mode.
- Deixar respostas HTML 403 fora do coexist adapter — superado para `operacao-producao`, porque a segurança estava correta mas a interface caía no layout legacy.

## Decisões humanas pendentes
- H001 P2 do `teste-sofa`: renovar a autorização quando dois aprovadores humanos distintos admin/professor estiverem disponíveis; o solicitante não pode aprovar a própria ativação.

## Decisões fechadas nesta emenda
- A navegação contextual usa tokens globais `--iff-wash`/`--iff-dark` para o item ativo.
- Em tema escuro, `.tab-git .legacy-content` normaliza assistente, cards de projetos, recursos, menus, formulários e controles claros para os tokens dark canônicos.
- O 403 de **Produção** é transformado pelo shell v2 sem alterar o código HTTP nem a regra de autorização.
- `versao_contrato` permanece 50, com entrada regressiva 1518 cobrindo Reconciliação→Código/Produção em viewport móvel.

## Pendências técnicas não humanas
- U14: **Gerenciar permissões** do Teste Sofá ainda possui divergência previamente observada de drawer vazio; não foi mexido na U16 por estar fora do escopo solicitado.
- Após H001: executar P2, validar artefato/HTTPS/terminal/stable URL e exercitar rollback real para P1.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — vazio após o fechamento da U16; nenhuma zona de exclusão permanece reservada.

## Competências ativas nesta unidade
- `cloudiff@0.1.12` — skill raiz, atualizada com L024/L025 após homologação viva.
- `desenvolvedor-de-software@15` — método PGH vigente.
- `github-incremental-reconciliation@7` — reconciliação incremental.
- `governanca-ontologica-de-skills@1.0.5` — política vigente.
- `telemetry-data-visualization@2` — macro global obrigatória.

## Falhas de portão por tipo de entrada
- `interface/tema`: shell da aba Código ficava dark, mas `.ci-section`, `.ci-step` e `.ci-project-card` continuavam brancos por CSS legacy hard-coded.
- `interface/erro-controlado`: Produção preservava 403, mas exibia HTML legacy cru em vez do shell moderno.

## Divergências da última reconciliação
### Corrigidas
- `portal/design/components.css`: bridge dark escopada a `.tab-git .legacy-content`, sem redesenhar outras tabs.
- `cloudif_portal_v2_coexist.py`: 403 de `operacao-producao` passa pelo shell canônico mantendo status 403.
- Deploy U16 base: `u16-reconciliacao-mobile-dark-b696e9c-20260904`.
- Deploy complementar Código dark: `u16-code-dark-6e59688-20260904`.
- Navegação viva 390 px: Reconciliação→Código por clique real manteve `data-theme=dark`, Código ativo com fundo `rgb(23, 53, 31)`, body `rgb(7, 17, 11)`, `whiteCount=0` e sem overflow horizontal na aba Código.
- Navegação viva para Produção: shell canônico, Produção ativa, mensagem `Projeto não autorizado.`, dark mode correto e HTTP 403 preservado.

### Pendentes fora do escopo
- Drawer vazio de **Gerenciar permissões** já registrado na U14.
- H001: gate humano de P2.

## Entradas aceitas nesta unidade
- 1518 — regressão de Reconciliação→Código/Produção em mobile/dark.
- `portal/design/components.css` — tokens dark do item ativo e bridge visual da tab Código.
- `cloudif_portal_v2_coexist.py` — adaptação visual do 403 de Produção preservando status.
- `portal/FROZEN_SURFACES.md` — emenda visual explicitamente autorizada.
- `skills/cloudiff/SKILL.md` — L024/L025 e versão 0.1.12.
- `competencias.yaml` — skill de projeto 0.1.12.

## Portões da unidade
- `U16_UNIT_TESTS=PASS`: 24/24 no conjunto final de regressões de Reconciliação/mobile/dark e contratos relacionados.
- `LIVE_CODE_DARK_CARDS=PASS`: todas as superfícies principais da aba Código usam dark mode; nenhuma superfície-alvo visível permanece `rgb(255,255,255)`.
- `LIVE_REAL_CLICK_RECONCILIATION_TO_CODE=PASS`: clique real do menu contextual até Código preserva dark mode e largura móvel.
- `LIVE_PRODUCTION_DENIAL_SHELL=PASS`: Produção permanece 403 e usa o shell moderno dark.
- `PY_COMPILE=PASS`, `DIFF_CHECK=PASS`, `SECRET_SCAN=PASS`.
- `DELTA_INVENTORY=PASS`, `LEARNING_PRESERVED=PASS`: catálogo permaneceu em `9b951d0d2f68a3ead190741fd5e8b4d6cc8e0a84`, sem delta nas skills consumidas.

## Próxima unidade
- Tratar separadamente **Gerenciar permissões**; quando os dois aprovadores humanos estiverem disponíveis, renovar P2 e concluir publicação + smoke + rollback.
