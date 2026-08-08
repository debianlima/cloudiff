# Build Broker Current

Componentes implantados no plano de controle e no host de hospedagem.

<!-- CLOUDIFF-AUTO-DOC:BEGIN -->

## Inventário automático de `components/control-plane/current-apps/build-broker-current`

Componentes implantados no plano de controle e no host de hospedagem.

| Item | Tipo | Finalidade |
|---|---|---|
| [`cloudif-build-broker.py`](cloudif-build-broker.py) | `.py` | Implementa `now`, `db`, `init_db`, `sanitize`, `idem`, `auth` e outros componentes. |
| [`cloudif_toolchain_lifecycle.py`](cloudif_toolchain_lifecycle.py) | `.py` | Implementa `configure`, `_require_configured`, `_image_record`, `reusable`, `plan`, `_request_for_plan` e outros componentes. |
| [`cloudif_toolchain_policy.py`](cloudif_toolchain_policy.py) | `.py` | Implementa `canonical`, `digest`, `load_catalog`, `safe_relative_path`, `_item_name_version`, `_resolve_catalog_items` e outros componentes. |

> Esta seção é gerada por `scripts/generate-directory-readmes.py`. Conteúdo manual fora dos marcadores é preservado.

<!-- CLOUDIFF-AUTO-DOC:END -->
