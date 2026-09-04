# Estado — 2026-09-04 — contrato v51

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a U17 fez somente o acabamento dark da aba **Código**, sem nova rota ou mudança funcional.
- A aba **Código** usa shell e cards escuros; identificadores e estados positivos usam o verde canônico do tema dark.
- `teste-sofa` permanece projeto descartável de QA; P2 continua dependente de duas aprovações humanas distintas admin/professor e deve ser renovada quando os aprovadores estiverem disponíveis.
- A skill de projeto vigente passa a `cloudiff@0.1.13`.

## Decisões superadas
- Considerar encerrada a correção dark quando apenas os cards grandes deixaram de ser brancos — superado após o navegador encontrar chips `<code>` e `.ci-pill` ainda claros.
- Usar `--surface-2` no bridge dark — superado porque esse token não existe no design system e a declaração era descartada, deixando fundo transparente.

## Decisões humanas pendentes
- H001 P2 do `teste-sofa`: renovar a autorização e obter duas decisões humanas distintas admin/professor, ambas diferentes do solicitante.

## Decisões fechadas nesta emenda
- Identificadores `<code>` da aba Código usam `--iff-wash` no fundo e `--iff-dark` no texto em dark mode.
- `Vinculado`, `Configurado` e `Online` usam o mesmo par canônico verde; estados neutros usam `--surface`/`--ink-2`.
- O ajuste é escopado a `.tab-git .legacy-content`.
- `versao_contrato` avançou para 51 e a entrada regressiva 1519 fixa esse acabamento.

## Pendências técnicas não humanas
- U14: **Gerenciar permissões** do Teste Sofá ainda possui divergência previamente observada de drawer vazio, fora do escopo desta unidade.
- Após H001: executar P2, smoke completo e rollback real para P1.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — vazio após o fechamento da U17; nenhuma zona de exclusão permanece reservada.

## Competências ativas nesta unidade
- `cloudiff@0.1.13` — skill raiz, atualizada com L026 após homologação viva.
- `desenvolvedor-de-software@15`.
- `github-incremental-reconciliation@7`.
- `governanca-ontologica-de-skills@1.0.5`.
- `telemetry-data-visualization@2`.

## Falhas de portão por tipo de entrada
- `interface/tema`: chips de slug/tenant e badges de estado continuavam claros sobre os cards dark.
- `interface/css`: token inexistente `--surface-2` gerava fallback transparente silencioso.

## Divergências da última reconciliação
### Corrigidas
- `portal/design/components.css`: bridge dark dos chips e badges usa somente tokens existentes.
- Deploy ativo: `u17-code-dark-tokens-64df100-20260904`.
- Chromium móvel dark: `teste-sofa`, `iff1742962-testesofa`, `Vinculado`, `Configurado` e `Online` ficaram em fundo `rgb(23, 53, 31)` e texto `rgb(149, 223, 163)`.
- `lightCount=0` entre os chips/badges alvo; largura da página permaneceu sem overflow horizontal.

### Pendentes fora do escopo
- Drawer vazio de **Gerenciar permissões**.
- Gate humano P2.

## Entradas aceitas nesta unidade
- 1519 — regressão dos identificadores e badges remanescentes da aba Código no tema escuro.
- `portal/design/components.css` — acabamento dark escopado à tab Git/Código.
- `portal/FROZEN_SURFACES.md` — emenda visual explicitamente autorizada.
- `skills/cloudiff/SKILL.md` — L026 e versão 0.1.13.
- `competencias.yaml` — skill de projeto 0.1.13.

## Portões da unidade
- `U17_REGRESSION_TESTS=PASS`: 19/19.
- `LIVE_CODE_CHIPS_THEME=PASS`: estilos computados corretos no Chromium dark e `lightCount=0`.
- `DIFF_CHECK=PASS`, `SECRET_SCAN=PASS`.
- `DELTA_INVENTORY=PASS`, `LEARNING_PRESERVED=PASS`: catálogo permaneceu em `9b951d0d2f68a3ead190741fd5e8b4d6cc8e0a84`, sem delta nas skills consumidas.

## Próxima unidade
- Tratar separadamente o drawer vazio de **Gerenciar permissões**; quando os aprovadores humanos estiverem disponíveis, renovar P2 e concluir publicação + smoke + rollback.
