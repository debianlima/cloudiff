# Lib

Componentes implantados no plano de controle e no host de hospedagem.

<!-- CLOUDIFF-AUTO-DOC:BEGIN -->

## Inventário automático de `components/control-plane/srv/cloudif/staging/lib`

Componentes implantados no plano de controle e no host de hospedagem.

| Item | Tipo | Finalidade |
|---|---|---|
| [`cloudif-common.sh`](cloudif-common.sh) | `.sh` | Automação Shell operacional da plataforma. |
| [`cloudif-supabase.sh`](cloudif-supabase.sh) | `.sh` | Automação Shell operacional da plataforma. |
| [`cloudif_ad_directory_module.py`](cloudif_ad_directory_module.py) | `.py` | Implementa `_db`, `_rows`, `_tables`, `_cols`, `_pick`, `setting_value` e outros componentes. |
| [`cloudif_ad_search_module.py`](cloudif_ad_search_module.py) | `.py` | Implementa `_db`, `_rows`, `_tables`, `_cols`, `_pick`, `_setting_value` e outros componentes. |
| [`cloudif_bancos_module.py`](cloudif_bancos_module.py) | `.py` | Implementa `h`, `read_env`, `db_path`, `add_tenant`, `list_tenants`, `render_bancos_style` e outros componentes. |
| [`cloudif_delete_git_komodo_action.py`](cloudif_delete_git_komodo_action.py) | `.py` | Implementa `h`, `read_env`, `db_path`, `forja_config`, `form_get`, `request_op` e outros componentes. |
| [`cloudif_frontend_v55.py`](cloudif_frontend_v55.py) | `.py` | Implementa `now`, `h`, `db`, `table_exists`, `db_one`, `db_all` e outros componentes. |
| [`cloudif_git_komodo_module.py`](cloudif_git_komodo_module.py) | `.py` | Implementa `h`, `read_env`, `refresh_public_host`, `db_rows`, `db_exec`, `table_cols` e outros componentes. |
| [`cloudif_machine_db.py`](cloudif_machine_db.py) | `.py` | Implementa `_pg_connect`, `PgConnection`, `connect`, `init_schema`, `table_columns`. |
| [`cloudif_onboarding_v2.py`](cloudif_onboarding_v2.py) | `.py` | Implementa `build_onboarding_v2`. |
| [`cloudif_portal_publications.py`](cloudif_portal_publications.py) | `.py` | Implementa `_env`, `_post`, `_project_allowed`, `_ensure_schema`, `_number`, `_clients` e outros componentes. |
| [`cloudif_project_acl_module.py`](cloudif_project_acl_module.py) | `.py` | Implementa `h`, `con`, `table_cols`, `pick`, `detect_acl_config`, `project_row` e outros componentes. |
| [`cloudif_project_action_safe.py`](cloudif_project_action_safe.py) | `.py` | Implementa `_log`, `h`, `slugify`, `now_stamp`, `user_from_headers`, `val` e outros componentes. |
| [`cloudif_project_provision_real.py`](cloudif_project_provision_real.py) | `.py` | Implementa `log`, `load_env_files`, `env`, `slugify`, `run`, `http_json` e outros componentes. |
| [`cloudif_project_provision_worker.py`](cloudif_project_provision_worker.py) | `.py` | Implementa `log`, `run`, `main`. |
| [`cloudif_publish_site_action.py`](cloudif_publish_site_action.py) | `.py` | Implementa `_read_env`, `_komodo_agent_config`, `_form_get`, `_http_post_json`, `_is_publish_op`, `handle_publish_site_action`. |
| [`cloudif_rbac.py`](cloudif_rbac.py) | `.py` | Implementa `_groups`, `_identities`, `is_global_admin`, `_level`, `_project_level`, `_tenant_level` e outros componentes. |
| [`cloudif_reconcile_client.py`](cloudif_reconcile_client.py) | `.py` | Implementa `now_utc`, `connect`, `ensure_schema`, `_safe_slug`, `enqueue`, `status` e outros componentes. |
| [`cloudif_release_manager.py`](cloudif_release_manager.py) | `.py` | Implementa `now_utc`, `parse_utc`, `read_env`, `connect`, `ensure_schema`, `safe_detail` e outros componentes. |
| [`cloudif_theme_module.py`](cloudif_theme_module.py) | `.py` | Implementa `render_theme_css`. |
| [`cloudif_ui_components.py`](cloudif_ui_components.py) | `.py` | Implementa `h`, `css`, `btn`, `pill`, `menu_tabs`, `banner` e outros componentes. |
| [`cloudif_ui_data.py`](cloudif_ui_data.py) | `.py` | Implementa `db_rows`, `discover_projects`, `discover_tenants`, `public_studio_url`, `deploy_url`, `tab_url` e outros componentes. |
| [`cloudif_ui_modular.py`](cloudif_ui_modular.py) | `.py` | Módulo Python da plataforma. |
| [`cloudif_ui_pages.py`](cloudif_ui_pages.py) | `.py` | Implementa `_v95_user_name`, `_v95_user_groups`, `_v95_is_admin`, `_v95_tenant_name`, `_v95_allowed_tenants`, `_v95_options` e outros componentes. |
| [`cloudif_ui_publications.py`](cloudif_ui_publications.py) | `.py` | Implementa `h`, `_rows`, `publication_panel`, `admin_publications`. |

> Esta seção é gerada por `scripts/generate-directory-readmes.py`. Conteúdo manual fora dos marcadores é preservado.

<!-- CLOUDIFF-AUTO-DOC:END -->
