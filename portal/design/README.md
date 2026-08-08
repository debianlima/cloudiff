# Design

Arquitetura modular, interface, configuração e testes do Portal.


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
