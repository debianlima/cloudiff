# Artifact Executor Current

Componentes implantados no host de runtime, Forgejo, Komodo e executores.

<!-- CLOUDIFF-AUTO-DOC:BEGIN -->

## Inventário automático de `components/runtime/current-apps/artifact-executor-current`

Componentes implantados no host de runtime, Forgejo, Komodo e executores.

| Item | Tipo | Finalidade |
|---|---|---|
| [`cloudif-artifact-executor.py`](cloudif-artifact-executor.py) | `.py` | Implementa `db`, `auth`, `sanitize`, `run`, `build`, `H`. |
| [`cloudif_multiservice_artifact.py`](cloudif_multiservice_artifact.py) | `.py` | Implementa `ArtifactError`, `sha256`, `canonical`, `load_env`, `safe_rel`, `normalize_command` e outros componentes. |
| [`cloudif_toolchain_policy.py`](cloudif_toolchain_policy.py) | `.py` | Implementa `canonical`, `digest`, `load_catalog`, `safe_relative_path`, `_item_name_version`, `_resolve_catalog_items` e outros componentes. |

> Esta seção é gerada por `scripts/generate-directory-readmes.py`. Conteúdo manual fora dos marcadores é preservado.

<!-- CLOUDIFF-AUTO-DOC:END -->
