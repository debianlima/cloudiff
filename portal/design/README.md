# Design

Arquitetura modular, interface, configuração e testes do Portal.


## U21 — Workspace de nuvem focado no projeto ativo

Direção aprovada em 2026-09-07: o Portal deixa de apresentar projetos como mosaico/feed de cartões e passa a tratar o projeto como contexto de trabalho. A seleção deve ser pesquisável e compacta; somente o projeto ativo expõe detalhes. Navegação contextual preserva `project=<slug>` entre telas. Temas claro e escuro usam superfícies neutras e o verde institucional como acento, não como preenchimento dominante. Informação secundária usa divulgação progressiva; ações destrutivas mostram alvo, impacto e estado da operação.

Portões: WCAG 2.2 AA, teclado/foco, sem atributos HTML duplicados, sem `!important` no CSS canônico, contexto ativo inequívoco, lista de projetos pesquisável e fluxo de exclusão reutilizável após erro de confirmação.

## Wizard W/H/P

Os estilos do wizard de publicação ficam no stylesheet canônico [`components.css`](components.css). Eles usam apenas tokens de [`tokens.css`](tokens.css), sem paleta paralela, sem `!important` e sem cores literais. Assim o mesmo componente acompanha automaticamente os temas Claro/Escuro e o layout mobile do Portal v2.

O JavaScript do wizard é entregue pelo Portal, mas o CSS **não** deve voltar a `<style>` inline: o adaptador v2 descarta estilos legados e serve os assets canônicos de `design/` em todas as abas modernas.

<!-- CLOUDIFF-AUTO-DOC:BEGIN -->

## Inventário automático de `portal/design`

Arquitetura modular, interface, configuração e testes do Portal.

| Item | Tipo | Finalidade |
|---|---|---|
| [`app.js`](app.js) | `.js` | Comportamento JavaScript da interface ou automação. |
| [`base.css`](base.css) | `.css` | Estilos da interface web. |
| [`components.css`](components.css) | `.css` | Estilos da interface web. |
| [`tokens.css`](tokens.css) | `.css` | Estilos da interface web. |

> Esta seção é gerada por `scripts/generate-directory-readmes.py`. Conteúdo manual fora dos marcadores é preservado.

<!-- CLOUDIFF-AUTO-DOC:END -->
