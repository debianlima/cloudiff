# Portal legado congelado

Snapshot do Portal em produção no início da migração v2. Não adicione novas
camadas de CSS nem funcionalidades aqui. Durante a coexistência, rotas ainda não
registradas na v2 continuam usando o legado.

<!-- CLOUDIFF-AUTO-DOC:BEGIN -->

## Inventário automático de `portal/legacy`

Arquitetura modular, interface, configuração e testes do Portal.

| Item | Tipo | Finalidade |
|---|---|---|
| [`cloudif-admin-portal-base.py`](cloudif-admin-portal-base.py) | `.py` | Implementa `now_iso`, `h`, `norm`, `slugify`, `parse_groups`, `db` e outros componentes. |
| [`cloudif-admin-portal.py`](cloudif-admin-portal.py) | `.py` | CloudIFF portal launcher with canonical authorization and UI normalization. |
| [`cloudif_ai_agents_guide.py`](cloudif_ai_agents_guide.py) | `.py` | Implementa `e`, `tools`, `links`, `guide_data`, `config_json`, `render`. |
| [`cloudif_approval_panel.py`](cloudif_approval_panel.py) | `.py` | Implementa `request`, `sanitize`, `filter_rows`, `fmt_epoch`, `badge`, `render`. |
| [`cloudif_portal_publications.py`](cloudif_portal_publications.py) | `.py` | Implementa `_env`, `_post`, `_project_allowed`, `_ensure_schema`, `_number`, `_clients` e outros componentes. |
| [`cloudif_portal_sections98.py`](cloudif_portal_sections98.py) | `.py` | Implementa `e`, `jload`, `dbcount`, `active`, `shell`, `cards` e outros componentes. |
| [`cloudif_production_operations_panel.py`](cloudif_production_operations_panel.py) | `.py` | Implementa `read_json`, `data`, `esc`, `badge`, `render`. |
| [`cloudif_project_capabilities_panel.py`](cloudif_project_capabilities_panel.py) | `.py` | Implementa `e`, `data`, `render`. |
| [`cloudif_project_identity_panel.py`](cloudif_project_identity_panel.py) | `.py` | Implementa `fetch`, `visible`, `badge`, `role_badge`, `permission_summary`, `approval_list` e outros componentes. |
| [`cloudif_promotion_panel.py`](cloudif_promotion_panel.py) | `.py` | Implementa `fetch`, `e`, `render`. |
| [`cloudif_publication_panel.py`](cloudif_publication_panel.py) | `.py` | Implementa `node24_status`, `data`, `render`. |
| [`cloudif_reconcile_panel.py`](cloudif_reconcile_panel.py) | `.py` | Implementa `e`, `data`, `render`. |
| [`cloudif_transaction_panel.py`](cloudif_transaction_panel.py) | `.py` | Implementa `fetch`, `fmt`, `esc`, `badge`, `render`. |
| [`cloudif_ui_publications.py`](cloudif_ui_publications.py) | `.py` | Implementa `h`, `_rows`, `_project_context`, `_project_information`, `publication_panel`, `admin_publications`. |
| [`cloudif_unique_pages98.py`](cloudif_unique_pages98.py) | `.py` | Implementa `e`, `load`, `hero`, `shell`, `agent_management`, `mcp_docs` e outros componentes. |

> Esta seção é gerada por `scripts/generate-directory-readmes.py`. Conteúdo manual fora dos marcadores é preservado.

<!-- CLOUDIFF-AUTO-DOC:END -->
