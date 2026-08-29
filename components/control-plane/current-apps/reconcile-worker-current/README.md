# Reconcile Worker Current

Componentes implantados no plano de controle e no host de hospedagem.

<!-- CLOUDIFF-AUTO-DOC:BEGIN -->

## Inventário automático de `components/control-plane/current-apps/reconcile-worker-current`

Componentes implantados no plano de controle e no host de hospedagem.

| Item | Tipo | Finalidade |
|---|---|---|
| [`cloudif-reconcile-worker.py`](cloudif-reconcile-worker.py) | `.py` | Implementa `read_env`, `forja_project`, `reconcile_project_runtime`, `db_container`, `internal_post`, `project_membership_snapshot` e outros componentes. |
| [`cloudif_reconcile_client.py`](cloudif_reconcile_client.py) | `.py` | Implementa `now_utc`, `connect`, `ensure_schema`, `_safe_slug`, `_contains_secret`, `_partition` e outros componentes. |

> Esta seção é gerada por `scripts/generate-directory-readmes.py`. Conteúdo manual fora dos marcadores é preservado.

<!-- CLOUDIFF-AUTO-DOC:END -->
## Diagnóstico de retry/dead-letter

O schema persiste somente contexto sanitizado da última falha: `last_error_type`, `last_error_stage`, `last_error_upstream`, `last_error_status`, `last_error_code` e `last_error_detail`. O `result_json` de dead-letter preserva `error_type`/`secrets_exposed=false` e acrescenta `diagnostic`. Tokens, passwords, Authorization/Bearer e userinfo de URL são redigidos antes de persistência. Uma execução bem-sucedida limpa os campos `last_error_*`.
