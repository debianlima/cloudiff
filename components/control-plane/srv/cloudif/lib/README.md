# Lib

Componentes implantados no plano de controle e no host de hospedagem.

<!-- CLOUDIFF-AUTO-DOC:BEGIN -->

## Inventário automático de `components/control-plane/srv/cloudif/lib`

Componentes implantados no plano de controle e no host de hospedagem.

| Item | Tipo | Finalidade |
|---|---|---|
| [`cloudif-common.sh`](cloudif-common.sh) | `.sh` | Automação Shell operacional da plataforma. |
| [`cloudif-supabase.sh`](cloudif-supabase.sh) | `.sh` | Automação Shell operacional da plataforma. |
| [`cloudif_ad_directory_module.py`](cloudif_ad_directory_module.py) | `.py` | Implementa `_db`, `_rows`, `_tables`, `_cols`, `_pick`, `setting_value` e outros componentes. |
| [`cloudif_ad_search_module.py`](cloudif_ad_search_module.py) | `.py` | Implementa `_db`, `_rows`, `_tables`, `_cols`, `_pick`, `_setting_value` e outros componentes. |
| [`cloudif_admin_project_delete.py`](cloudif_admin_project_delete.py) | `.py` | Implementa `issue_wizard_token`, `consume_wizard_token`, `_confirmation_matches`, `_job_write`, `job_status`, `start_job` e outros componentes. |
| [`cloudif_admin_tenant_delete.py`](cloudif_admin_tenant_delete.py) | `.py` | Safe, asynchronous tenant/database deletion for CloudIFF. |
| [`cloudif_bancos_module.py`](cloudif_bancos_module.py) | `.py` | Implementa `h`, `read_env`, `db_path`, `add_tenant`, `list_tenants`, `render_bancos_style` e outros componentes. |
| [`cloudif_delete_git_komodo_action.py`](cloudif_delete_git_komodo_action.py) | `.py` | Implementa `h`, `read_env`, `db_path`, `forja_config`, `form_get`, `request_op` e outros componentes. |
| [`cloudif_frontend_v55.py`](cloudif_frontend_v55.py) | `.py` | Implementa `now`, `h`, `db`, `table_exists`, `db_one`, `db_all` e outros componentes. |
| [`cloudif_git_komodo_module.py`](cloudif_git_komodo_module.py) | `.py` | Implementa `h`, `read_env`, `refresh_public_host`, `db_rows`, `db_exec`, `table_cols` e outros componentes. |
| [`cloudif_machine_db.py`](cloudif_machine_db.py) | `.py` | Implementa `_pg_connect`, `PgConnection`, `connect`, `init_schema`, `table_columns`. |
| [`cloudif_multiservice_preview_portal.py`](cloudif_multiservice_preview_portal.py) | `.py` | Implementa `_send`, `_json`, `handle_preview_request`. |
| [`cloudif_onboarding_v2.py`](cloudif_onboarding_v2.py) | `.py` | Código inicial publicado em todo projeto novo da CloudIFF. |
| [`cloudif_portal_artifact_upload.py`](cloudif_portal_artifact_upload.py) | `.py` | Implementa `_json_body`, `ticket_status`, `project_allowed`, `safe_metadata`, `forward_upload`, `render_page`. |
| [`cloudif_portal_publications.py`](cloudif_portal_publications.py) | `.py` | Implementa `_env`, `_post`, `_publication_error`, `_project_allowed`, `_ensure_schema`, `_number` e outros componentes. |
| [`cloudif_portal_v2_coexist.py`](cloudif_portal_v2_coexist.py) | `.py` | CloudIFF Portal v2 coexistence and auto-recovery adapter |
| [`cloudif_project_acl_module.py`](cloudif_project_acl_module.py) | `.py` | Implementa `h`, `con`, `table_cols`, `pick`, `detect_acl_config`, `project_row` e outros componentes. |
| [`cloudif_project_action_safe.py`](cloudif_project_action_safe.py) | `.py` | Implementa `_log`, `h`, `slugify`, `now_stamp`, `user_from_headers`, `val` e outros componentes. |
| [`cloudif_project_config_events.py`](cloudif_project_config_events.py) | `.py` | Implementa `_env`, `_safe_details`, `event_for_reconcile`, `notify`. |
| [`cloudif_project_environment_web.py`](cloudif_project_environment_web.py) | `.py` | Implementa `_env_file_value`, `_json_call`, `_control_project`, `authorization`, `_config_path`, `_config` e outros componentes. |
| [`cloudif_project_environments_overview.py`](cloudif_project_environments_overview.py) | `.py` | Implementa `_config`, `_runtime`, `_preview`, `_production`, `overview`, `handle_get`. |
| [`cloudif_project_observability_web.py`](cloudif_project_observability_web.py) | `.py` | Implementa `_call`, `handle_get`. |
| [`cloudif_project_provision_real.py`](cloudif_project_provision_real.py) | `.py` | Implementa `log`, `load_env_files`, `env`, `slugify`, `run`, `http_json` e outros componentes. |
| [`cloudif_project_provision_recover.py`](cloudif_project_provision_recover.py) | `.py` | Implementa `unit_name`, `parse_time`, `active`, `launch`, `main`. |
| [`cloudif_project_provision_status.py`](cloudif_project_provision_status.py) | `.py` | Implementa `_load`, `_connect`, `_project`, `_publication`, `_public_number`, `_jobs` e outros componentes. |
| [`cloudif_project_provision_worker.py`](cloudif_project_provision_worker.py) | `.py` | Implementa `log`, `atomic_job`, `set_state`, `run`, `json_output`, `require_timer` e outros componentes. |
| [`cloudif_project_publication_config.py`](cloudif_project_publication_config.py) | `.py` | Implementa `_env`, `_json`, `_config_headers`, `_komodo_headers`, `_environment_name`, `_effective` e outros componentes. |
| [`cloudif_project_runtime_reconcile_web.py`](cloudif_project_runtime_reconcile_web.py) | `.py` | Implementa `_call`, `handle_get`, `handle_post`. |
| [`cloudif_project_secret_web.py`](cloudif_project_secret_web.py) | `.py` | Implementa `_config`, `_plan`, `_require_read`, `_require_write`, `_require_secret_read`, `_approval_metadata` e outros componentes. |
| [`cloudif_project_toolchain_web.py`](cloudif_project_toolchain_web.py) | `.py` | Implementa `_build`, `_require_write`, `_plan`, `_activation_plan`, `_create_approval`, `request_build_approval` e outros componentes. |
| [`cloudif_publish_site_action.py`](cloudif_publish_site_action.py) | `.py` | Implementa `_read_env`, `_komodo_agent_config`, `_form_get`, `_http_post_json`, `_is_publish_op`, `handle_publish_site_action`. |
| [`cloudif_rbac.py`](cloudif_rbac.py) | `.py` | Implementa `_groups`, `_identities`, `is_global_admin`, `_level`, `_project_level`, `_tenant_level` e outros componentes. |
| [`cloudif_reconcile_client.py`](cloudif_reconcile_client.py) | `.py` | Implementa `now_utc`, `connect`, `ensure_schema`, `_safe_slug`, `_contains_secret`, `_partition` e outros componentes. |
| [`cloudif_release_manager.py`](cloudif_release_manager.py) | `.py` | Implementa `now_utc`, `parse_utc`, `read_env`, `connect`, `ensure_schema`, `safe_detail` e outros componentes. |
| [`cloudif_theme_module.py`](cloudif_theme_module.py) | `.py` | Implementa `render_theme_css`. |
| [`cloudif_ui_components.py`](cloudif_ui_components.py) | `.py` | Implementa `h`, `css`, `btn`, `pill`, `menu_tabs`, `banner` e outros componentes. |
| [`cloudif_ui_data.py`](cloudif_ui_data.py) | `.py` | Implementa `db_rows`, `discover_projects`, `discover_tenants`, `public_studio_url`, `deploy_url`, `tab_url` e outros componentes. |
| [`cloudif_ui_modular.py`](cloudif_ui_modular.py) | `.py` | Módulo Python da plataforma. |
| [`cloudif_ui_pages.py`](cloudif_ui_pages.py) | `.py` | Implementa `_v95_user_name`, `_v95_user_groups`, `_v95_is_admin`, `_v95_tenant_name`, `_v95_allowed_tenants`, `_v95_options` e outros componentes. |
| [`cloudif_ui_publications.py`](cloudif_ui_publications.py) | `.py` | Implementa `h`, `_rows`, `_runtime_from_job`, `_komodo_web_status`, `_project_context`, `_project_information` e outros componentes. |
| [`sitecustomize.py`](sitecustomize.py) | `.py` | Portal-scoped startup hook |

> Esta seção é gerada por `scripts/generate-directory-readmes.py`. Conteúdo manual fora dos marcadores é preservado.

<!-- CLOUDIFF-AUTO-DOC:END -->
