# Project Runtime Reconciler

Compara estado desejado e observado sem executar efeitos por conta própria. Estados canônicos: `synchronized`, `pending-rebuild`, `pending-restart`, `missing-variable`, `image-outdated`, `configuration-drift`, `unhealthy` e `blocked`.

Produção nunca recebe reparo destrutivo automático. Valores e referências de segredos não entram no banco deste reconciliador.
