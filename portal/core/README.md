# Core

Arquitetura modular, interface, configuração e testes do Portal.

<!-- CLOUDIFF-AUTO-DOC:BEGIN -->

## Inventário automático de `portal/core`

Arquitetura modular, interface, configuração e testes do Portal.

| Item | Tipo | Finalidade |
|---|---|---|
| [`__init__.py`](__init__.py) | `.py` | Shared Portal v2 core services. |
| [`auth.py`](auth.py) | `.py` | Authentication identity contract; Authentik remains the source of truth. |
| [`dispatch.py`](dispatch.py) | `.py` | Edge dispatcher: resolve route, enforce permission once, then call the view |
| [`errors.py`](errors.py) | `.py` | User-facing empty and error states. |
| [`http.py`](http.py) | `.py` | HTTP request/response contracts shared by migrated Portal v2 modules |
| [`legacy_bridge.py`](legacy_bridge.py) | `.py` | Bridge to the v1 panel modules that carry real business logic |
| [`legacy_shell.py`](legacy_shell.py) | `.py` | Adapt legacy GET pages into the canonical Portal v2 shell |
| [`rbac.py`](rbac.py) | `.py` | Permission decisions for Portal v2 |
| [`security.py`](security.py) | `.py` | Edge security primitives: CSRF and same-origin, reproduced from the v1 |

> Esta seção é gerada por `scripts/generate-directory-readmes.py`. Conteúdo manual fora dos marcadores é preservado.

<!-- CLOUDIFF-AUTO-DOC:END -->
