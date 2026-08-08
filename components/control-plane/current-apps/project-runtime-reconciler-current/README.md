# Project Runtime Reconciler

Compara estado desejado e observado sem executar efeitos por conta própria. Estados canônicos: `synchronized`, `pending-rebuild`, `pending-restart`, `missing-variable`, `image-outdated`, `configuration-drift`, `unhealthy` e `blocked`.

Produção nunca recebe reparo destrutivo automático. Valores e referências de segredos não entram no banco deste reconciliador.

<!-- CLOUDIFF-AUTO-DOC:BEGIN -->

## Inventário automático de `components/control-plane/current-apps/project-runtime-reconciler-current`

Componentes implantados no plano de controle e no host de hospedagem.

| Item | Tipo | Finalidade |
|---|---|---|
| [`cloudif-project-runtime-reconciler.py`](cloudif-project-runtime-reconciler.py) | `.py` | Implementa `now`, `canonical`, `db`, `init_db`, `_json_call`, `project_slugs` e outros componentes. |

> Esta seção é gerada por `scripts/generate-directory-readmes.py`. Conteúdo manual fora dos marcadores é preservado.

<!-- CLOUDIFF-AUTO-DOC:END -->
