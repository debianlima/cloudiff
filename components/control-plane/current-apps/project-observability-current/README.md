# Project Observability

Serviço somente leitura que consolida runtime drift, ambiente/segredos e build/toolchain. Expõe snapshot JSON, alertas e métricas Prometheus. Nunca retorna valores ou referências de segredos e nunca executa efeitos.

<!-- CLOUDIFF-AUTO-DOC:BEGIN -->

## Inventário automático de `components/control-plane/current-apps/project-observability-current`

Componentes implantados no plano de controle e no host de hospedagem.

| Item | Tipo | Finalidade |
|---|---|---|
| [`cloudif-project-observability.py`](cloudif-project-observability.py) | `.py` | Implementa `now`, `_ro`, `_rows`, `_table_exists`, `_table_columns`, `_safe_json` e outros componentes. |

> Esta seção é gerada por `scripts/generate-directory-readmes.py`. Conteúdo manual fora dos marcadores é preservado.

<!-- CLOUDIFF-AUTO-DOC:END -->
