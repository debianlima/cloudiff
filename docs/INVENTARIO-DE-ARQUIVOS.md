# Inventário de arquivos

Este catálogo descreve **1156 arquivos versionados**. Ele é regenerado pelo script de documentação.

| Caminho | Finalidade |
|---|---|
| [`.github/workflows/README.md`](../.github/workflows/README.md) | Documentação deste diretório. |
| [`.github/workflows/validate.yml`](../.github/workflows/validate.yml) | Configuração declarativa YAML. |
| [`.gitignore`](../.gitignore) | Arquivo de suporte da plataforma. |
| [`README.md`](../README.md) | Documentação deste diretório. |
| [`SECURITY.md`](../SECURITY.md) | Documento técnico ou operacional. |
| [`components/README.md`](../components/README.md) | Documentação deste diretório. |
| [`components/control-plane/README.md`](../components/control-plane/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/README.md`](../components/control-plane/current-apps/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/agent-controller-current/README.md`](../components/control-plane/current-apps/agent-controller-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/agent-controller-current/cloudif-agent-controller-run.sh`](../components/control-plane/current-apps/agent-controller-current/cloudif-agent-controller-run.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/current-apps/agent-controller-current/cloudif-agent-controller.py`](../components/control-plane/current-apps/agent-controller-current/cloudif-agent-controller.py) | Implementa `now`, `env`, `api`, `atomic`, `partition`, `coalesce` e outros componentes. |
| [`components/control-plane/current-apps/agent-registry-current/README.md`](../components/control-plane/current-apps/agent-registry-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/agent-registry-current/cloudif-agent-registry.py`](../components/control-plane/current-apps/agent-registry-current/cloudif-agent-registry.py) | Implementa `c`, `init`, `hash_token`, `role_coherent`, `admin`, `H`. |
| [`components/control-plane/current-apps/approvals-current/README.md`](../components/control-plane/current-apps/approvals-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/approvals-current/cloudif-approval-api.py`](../components/control-plane/current-apps/approvals-current/cloudif-approval-api.py) | Implementa `c`, `init`, `auth`, `expire_rows`, `H`. |
| [`components/control-plane/current-apps/approvals-current/cloudif_approval_policy.py`](../components/control-plane/current-apps/approvals-current/cloudif_approval_policy.py) | Implementa `init_tables`, `active_policy`, `request_persistent`, `pending_request`, `activate_from_approval`, `list_policies` e outros componentes. |
| [`components/control-plane/current-apps/audit-current/README.md`](../components/control-plane/current-apps/audit-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/audit-current/cloudif-academic-audit-api.py`](../components/control-plane/current-apps/audit-current/cloudif-academic-audit-api.py) | Implementa `con`, `init`, `auth`, `H`. |
| [`components/control-plane/current-apps/build-broker-current/README.md`](../components/control-plane/current-apps/build-broker-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/build-broker-current/cloudif-build-broker.py`](../components/control-plane/current-apps/build-broker-current/cloudif-build-broker.py) | Implementa `now`, `db`, `init_db`, `sanitize`, `idem`, `auth` e outros componentes. |
| [`components/control-plane/current-apps/build-broker-current/cloudif_toolchain_lifecycle.py`](../components/control-plane/current-apps/build-broker-current/cloudif_toolchain_lifecycle.py) | Implementa `configure`, `_require_configured`, `_image_record`, `reusable`, `plan`, `_request_for_plan` e outros componentes. |
| [`components/control-plane/current-apps/build-broker-current/cloudif_toolchain_policy.py`](../components/control-plane/current-apps/build-broker-current/cloudif_toolchain_policy.py) | Implementa `canonical`, `digest`, `load_catalog`, `safe_relative_path`, `_item_name_version`, `_resolve_catalog_items` e outros componentes. |
| [`components/control-plane/current-apps/control-dashboard-current/README.md`](../components/control-plane/current-apps/control-dashboard-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/control-dashboard-current/cloudif-control-dashboard.py`](../components/control-plane/current-apps/control-dashboard-current/cloudif-control-dashboard.py) | Implementa `get`, `access_snapshot`, `visible`, `data`, `page`, `H`. |
| [`components/control-plane/current-apps/control-plane-smoke-current/README.md`](../components/control-plane/current-apps/control-plane-smoke-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/control-plane-smoke-current/cloudif-control-plane-smoke.py`](../components/control-plane/current-apps/control-plane-smoke-current/cloudif-control-plane-smoke.py) | Implementa `env`, `http`. |
| [`components/control-plane/current-apps/deployment-broker-current/README.md`](../components/control-plane/current-apps/deployment-broker-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/deployment-broker-current/cloudif-deployment-broker.py`](../components/control-plane/current-apps/deployment-broker-current/cloudif-deployment-broker.py) | Implementa `send`, `auth`, `body`, `idem_connect`, `idem_digest`, `idem_begin` e outros componentes. |
| [`components/control-plane/current-apps/evaluations-current/README.md`](../components/control-plane/current-apps/evaluations-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/evaluations-current/cloudif-evaluation-api.py`](../components/control-plane/current-apps/evaluations-current/cloudif-evaluation-api.py) | Implementa `c`, `init`, `auth`, `audit_events`, `H`. |
| [`components/control-plane/current-apps/mcp-gateway-current/README.md`](../components/control-plane/current-apps/mcp-gateway-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py`](../components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py) | Implementa `_agent_clients`, `_oauth_client`, `_client_projects`, `_header_groups`, `_public_oauth_client`, `_callback_mode` e outros componentes. |
| [`components/control-plane/current-apps/monitor-current/README.md`](../components/control-plane/current-apps/monitor-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/monitor-current/cloudif-monitor-api.py`](../components/control-plane/current-apps/monitor-current/cloudif-monitor-api.py) | Implementa `rows`, `q`, `transactions`, `promotions`, `H`. |
| [`components/control-plane/current-apps/monitor-current/cloudif-monitor-collector.py`](../components/control-plane/current-apps/monitor-current/cloudif-monitor-collector.py) | Implementa `env`, `req`. |
| [`components/control-plane/current-apps/multiservice-preview-current/README.md`](../components/control-plane/current-apps/multiservice-preview-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/multiservice-preview-current/cloudif-multiservice-preview-broker.py`](../components/control-plane/current-apps/multiservice-preview-current/cloudif-multiservice-preview-broker.py) | Implementa `BrokerError`, `canonical`, `db`, `init_db`, `internal`, `json_internal` e outros componentes. |
| [`components/control-plane/current-apps/notifications-current/README.md`](../components/control-plane/current-apps/notifications-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/notifications-current/cloudif-notification-api.py`](../components/control-plane/current-apps/notifications-current/cloudif-notification-api.py) | Implementa `connect`, `init`, `rows`, `H`. |
| [`components/control-plane/current-apps/notifications-current/cloudif-notification-evaluator.py`](../components/control-plane/current-apps/notifications-current/cloudif-notification-evaluator.py) | Implementa `get`. |
| [`components/control-plane/current-apps/portal-current/README.md`](../components/control-plane/current-apps/portal-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py`](../components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py) | Implementa `now_iso`, `h`, `norm`, `slugify`, `parse_groups`, `_ensure_db_anchor` e outros componentes. |
| [`components/control-plane/current-apps/portal-current/cloudif-admin-portal.py`](../components/control-plane/current-apps/portal-current/cloudif-admin-portal.py) | CloudIFF portal launcher with canonical authorization and UI normalization. |
| [`components/control-plane/current-apps/portal-current/cloudif_ai_agents_guide.py`](../components/control-plane/current-apps/portal-current/cloudif_ai_agents_guide.py) | Implementa `e`, `tools`, `links`, `guide_data`, `oauth_fields`, `actions_schema_url` e outros componentes. |
| [`components/control-plane/current-apps/portal-current/cloudif_approval_panel.py`](../components/control-plane/current-apps/portal-current/cloudif_approval_panel.py) | Implementa `request`, `sanitize`, `filter_rows`, `sanitize_policy`, `filter_policies`, `fmt_epoch` e outros componentes. |
| [`components/control-plane/current-apps/portal-current/cloudif_portal_publications.py`](../components/control-plane/current-apps/portal-current/cloudif_portal_publications.py) | Implementa `_env`, `_post`, `_publication_error`, `_project_allowed`, `_ensure_schema`, `_number` e outros componentes. |
| [`components/control-plane/current-apps/portal-current/cloudif_portal_sections98.py`](../components/control-plane/current-apps/portal-current/cloudif_portal_sections98.py) | Implementa `e`, `jload`, `dbcount`, `active`, `shell`, `cards` e outros componentes. |
| [`components/control-plane/current-apps/portal-current/cloudif_production_operations_panel.py`](../components/control-plane/current-apps/portal-current/cloudif_production_operations_panel.py) | Implementa `read_json`, `data`, `esc`, `badge`, `render`. |
| [`components/control-plane/current-apps/portal-current/cloudif_project_capabilities_panel.py`](../components/control-plane/current-apps/portal-current/cloudif_project_capabilities_panel.py) | Implementa `e`, `data`, `render`. |
| [`components/control-plane/current-apps/portal-current/cloudif_project_identity_panel.py`](../components/control-plane/current-apps/portal-current/cloudif_project_identity_panel.py) | Implementa `fetch`, `visible`, `badge`, `role_badge`, `permission_summary`, `approval_list` e outros componentes. |
| [`components/control-plane/current-apps/portal-current/cloudif_promotion_panel.py`](../components/control-plane/current-apps/portal-current/cloudif_promotion_panel.py) | Implementa `fetch`, `e`, `render`. |
| [`components/control-plane/current-apps/portal-current/cloudif_publication_panel.py`](../components/control-plane/current-apps/portal-current/cloudif_publication_panel.py) | Implementa `node24_status`, `data`, `render`. |
| [`components/control-plane/current-apps/portal-current/cloudif_reconcile_panel.py`](../components/control-plane/current-apps/portal-current/cloudif_reconcile_panel.py) | Implementa `e`, `data`, `render`. |
| [`components/control-plane/current-apps/portal-current/cloudif_transaction_panel.py`](../components/control-plane/current-apps/portal-current/cloudif_transaction_panel.py) | Implementa `fetch`, `fmt`, `esc`, `badge`, `render`. |
| [`components/control-plane/current-apps/portal-current/cloudif_ui_publications.py`](../components/control-plane/current-apps/portal-current/cloudif_ui_publications.py) | Implementa `h`, `_rows`, `_runtime_from_job`, `_komodo_web_status`, `_project_context`, `_project_information` e outros componentes. |
| [`components/control-plane/current-apps/portal-current/cloudif_unique_pages98.py`](../components/control-plane/current-apps/portal-current/cloudif_unique_pages98.py) | Implementa `e`, `load`, `hero`, `shell`, `agent_management`, `mcp_docs` e outros componentes. |
| [`components/control-plane/current-apps/preview-broker-current/README.md`](../components/control-plane/current-apps/preview-broker-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/preview-broker-current/cloudif-preview-broker.py`](../components/control-plane/current-apps/preview-broker-current/cloudif-preview-broker.py) | Implementa `now`, `db`, `auth`, `cleanup_auth`, `executor_call`, `artifact` e outros componentes. |
| [`components/control-plane/current-apps/preview-broker-current/cloudif-preview-cleanup-client.py`](../components/control-plane/current-apps/preview-broker-current/cloudif-preview-cleanup-client.py) | Módulo Python da plataforma. |
| [`components/control-plane/current-apps/production-window-guard-current/README.md`](../components/control-plane/current-apps/production-window-guard-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/production-window-guard-current/cloudif-production-window-guard.py`](../components/control-plane/current-apps/production-window-guard-current/cloudif-production-window-guard.py) | Implementa `utc`, `atomic_json`, `alert`, `reseal`, `check`. |
| [`components/control-plane/current-apps/project-capabilities-current/README.md`](../components/control-plane/current-apps/project-capabilities-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/project-capabilities-current/cloudif-project-capabilities.py`](../components/control-plane/current-apps/project-capabilities-current/cloudif-project-capabilities.py) | Implementa `assignment_nodes`, `safe_value`, `assigned`, `load_catalog`, `connector_for`, `classify` e outros componentes. |
| [`components/control-plane/current-apps/project-config-controller-current/README.md`](../components/control-plane/current-apps/project-config-controller-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/project-config-controller-current/cloudif-project-config-controller.py`](../components/control-plane/current-apps/project-config-controller-current/cloudif-project-config-controller.py) | Implementa `ManifestResult`, `canonical`, `digest`, `now`, `load_schema`, `db_conn` e outros componentes. |
| [`components/control-plane/current-apps/project-config-controller-current/cloudif_project_environment.py`](../components/control-plane/current-apps/project-config-controller-current/cloudif_project_environment.py) | Implementa `environment_request_contract`, `actionable_request_error`, `now`, `canonical`, `digest`, `db` e outros componentes. |
| [`components/control-plane/current-apps/project-config-controller-current/cloudif_project_secret_store.py`](../components/control-plane/current-apps/project-config-controller-current/cloudif_project_secret_store.py) | Implementa `now`, `canonical`, `digest`, `db`, `init_db`, `_secure_key` e outros componentes. |
| [`components/control-plane/current-apps/project-config-reconciler-current/README.md`](../components/control-plane/current-apps/project-config-reconciler-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/project-config-reconciler-current/cloudif-project-config-reconciler.py`](../components/control-plane/current-apps/project-config-reconciler-current/cloudif-project-config-reconciler.py) | Implementa `now`, `connect`, `init_db`, `canonical`, `acl_snapshot`, `latest_build` e outros componentes. |
| [`components/control-plane/current-apps/project-observability-current/README.md`](../components/control-plane/current-apps/project-observability-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/project-observability-current/cloudif-project-observability.py`](../components/control-plane/current-apps/project-observability-current/cloudif-project-observability.py) | Implementa `now`, `_ro`, `_rows`, `_table_exists`, `_table_columns`, `_safe_json` e outros componentes. |
| [`components/control-plane/current-apps/project-onboarding-current/README.md`](../components/control-plane/current-apps/project-onboarding-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/project-onboarding-current/cloudif-project-onboarding-run.py`](../components/control-plane/current-apps/project-onboarding-current/cloudif-project-onboarding-run.py) | Módulo Python da plataforma. |
| [`components/control-plane/current-apps/project-onboarding-current/cloudif-project-onboarding.py`](../components/control-plane/current-apps/project-onboarding-current/cloudif-project-onboarding.py) | Implementa `now`, `cid`, `conn`, `init`, `api`, `external` e outros componentes. |
| [`components/control-plane/current-apps/project-runtime-reconciler-current/README.md`](../components/control-plane/current-apps/project-runtime-reconciler-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/project-runtime-reconciler-current/cloudif-project-runtime-reconciler.py`](../components/control-plane/current-apps/project-runtime-reconciler-current/cloudif-project-runtime-reconciler.py) | Implementa `now`, `canonical`, `db`, `init_db`, `_json_call`, `project_slugs` e outros componentes. |
| [`components/control-plane/current-apps/project-state-reconcile-current/README.md`](../components/control-plane/current-apps/project-state-reconcile-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/project-state-reconcile-current/cloudif-project-state-reconcile.py`](../components/control-plane/current-apps/project-state-reconcile-current/cloudif-project-state-reconcile.py) | Implementa `now`, `load_json`, `load_json_text`, `sha_file`, `atomic_write`, `onboarding_rows` e outros componentes. |
| [`components/control-plane/current-apps/reconcile-worker-current/README.md`](../components/control-plane/current-apps/reconcile-worker-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/reconcile-worker-current/cloudif-reconcile-worker.py`](../components/control-plane/current-apps/reconcile-worker-current/cloudif-reconcile-worker.py) | Implementa `read_env`, `forja_project`, `reconcile_project_runtime`, `db_container`, `internal_post`, `project_membership_snapshot` e outros componentes. |
| [`components/control-plane/current-apps/reconcile-worker-current/cloudif_reconcile_client.py`](../components/control-plane/current-apps/reconcile-worker-current/cloudif_reconcile_client.py) | Implementa `now_utc`, `connect`, `ensure_schema`, `_safe_slug`, `_contains_secret`, `_partition` e outros componentes. |
| [`components/control-plane/current-apps/runtime-policy-current/README.md`](../components/control-plane/current-apps/runtime-policy-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/runtime-policy-current/cloudif-runtime-policy.py`](../components/control-plane/current-apps/runtime-policy-current/cloudif-runtime-policy.py) | Implementa `load`, `digest`, `load_node_execution`, `load_node24_homologation`, `detect`, `plan` e outros componentes. |
| [`components/control-plane/current-apps/supabase-mcp-broker-current/README.md`](../components/control-plane/current-apps/supabase-mcp-broker-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/supabase-mcp-broker-current/cloudif-supabase-mcp-broker.py`](../components/control-plane/current-apps/supabase-mcp-broker-current/cloudif-supabase-mcp-broker.py) | Implementa `db_conn`, `init_state`, `read_env`, `is_secret_name`, `mask_secret`, `project_context` e outros componentes. |
| [`components/control-plane/current-apps/supabase-onboarding-broker-current/README.md`](../components/control-plane/current-apps/supabase-onboarding-broker-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/supabase-onboarding-broker-current/cloudif-supabase-onboarding-broker.py`](../components/control-plane/current-apps/supabase-onboarding-broker-current/cloudif-supabase-onboarding-broker.py) | Implementa `send`, `project`, `H`. |
| [`components/control-plane/current-apps/transaction-reconciler-current/README.md`](../components/control-plane/current-apps/transaction-reconciler-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/transaction-reconciler-current/cloudif-transaction-reconciler.py`](../components/control-plane/current-apps/transaction-reconciler-current/cloudif-transaction-reconciler.py) | Implementa `api_get`, `ro`, `iso_age`, `main`. |
| [`components/control-plane/current-apps/workspace-broker-current/README.md`](../components/control-plane/current-apps/workspace-broker-current/README.md) | Documentação deste diretório. |
| [`components/control-plane/current-apps/workspace-broker-current/cloudif-workspace-broker.py`](../components/control-plane/current-apps/workspace-broker-current/cloudif-workspace-broker.py) | Implementa `docker`, `base_container_args`, `probe`, `fetch_archive`, `safe_extract`, `detect_technologies` e outros componentes. |
| [`components/control-plane/current-apps/workspace-broker-current/cloudif_change_set.py`](../components/control-plane/current-apps/workspace-broker-current/cloudif_change_set.py) | Implementa `ChangeSetError`, `sha256`, `canonical`, `change_set_digest`, `normalize_path`, `decode_content` e outros componentes. |
| [`components/control-plane/current-apps/workspace-broker-current/cloudif_multitech_detector.py`](../components/control-plane/current-apps/workspace-broker-current/cloudif_multitech_detector.py) | Implementa `path_allowed`, `safe_json_file`, `safe_yaml_file`, `service_name`, `node_version`, `node_component` e outros componentes. |
| [`components/control-plane/current-apps/workspace-broker-current/cloudif_workspace_artifact.py`](../components/control-plane/current-apps/workspace-broker-current/cloudif_workspace_artifact.py) | Implementa `_artifact_lock`, `ArtifactError`, `_root`, `_dir`, `_meta_path`, `_payload_path` e outros componentes. |
| [`components/control-plane/etc/README.md`](../components/control-plane/etc/README.md) | Documentação deste diretório. |
| [`components/control-plane/etc/cloudif-multiservice-preview.env.example`](../components/control-plane/etc/cloudif-multiservice-preview.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`components/control-plane/etc/cloudif-project-config-controller.env.example`](../components/control-plane/etc/cloudif-project-config-controller.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`components/control-plane/etc/cloudif-project-config-reconciler.env.example`](../components/control-plane/etc/cloudif-project-config-reconciler.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`components/control-plane/etc/cloudif-supabase-mcp-broker.env.example`](../components/control-plane/etc/cloudif-supabase-mcp-broker.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`components/control-plane/etc/cloudif/README.md`](../components/control-plane/etc/cloudif/README.md) | Documentação deste diretório. |
| [`components/control-plane/etc/cloudif/schemas/README.md`](../components/control-plane/etc/cloudif/schemas/README.md) | Documentação deste diretório. |
| [`components/control-plane/etc/cloudif/schemas/cloudiff-v1.schema.json`](../components/control-plane/etc/cloudif/schemas/cloudiff-v1.schema.json) | Esquema ou contrato de dados em JSON. |
| [`components/control-plane/etc/cloudif/toolchain-catalog-v1.json`](../components/control-plane/etc/cloudif/toolchain-catalog-v1.json) | Configuração, inventário, evidência ou estado serializado em JSON. |
| [`components/control-plane/etc/systemd/README.md`](../components/control-plane/etc/systemd/README.md) | Documentação deste diretório. |
| [`components/control-plane/etc/systemd/system/README.md`](../components/control-plane/etc/systemd/system/README.md) | Documentação deste diretório. |
| [`components/control-plane/etc/systemd/system/cloudif-academic-audit.service`](../components/control-plane/etc/systemd/system/cloudif-academic-audit.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-admin-portal-staging.service`](../components/control-plane/etc/systemd/system/cloudif-admin-portal-staging.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-admin-portal.service`](../components/control-plane/etc/systemd/system/cloudif-admin-portal.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-admin-portal.service.d/20-security.conf`](../components/control-plane/etc/systemd/system/cloudif-admin-portal.service.d/20-security.conf) | Configuração de serviço, proxy ou aplicação. |
| [`components/control-plane/etc/systemd/system/cloudif-admin-portal.service.d/README.md`](../components/control-plane/etc/systemd/system/cloudif-admin-portal.service.d/README.md) | Documentação deste diretório. |
| [`components/control-plane/etc/systemd/system/cloudif-admin-portal.service.d/v2.conf`](../components/control-plane/etc/systemd/system/cloudif-admin-portal.service.d/v2.conf) | Configuração de serviço, proxy ou aplicação. |
| [`components/control-plane/etc/systemd/system/cloudif-agent-controller.path`](../components/control-plane/etc/systemd/system/cloudif-agent-controller.path) | Arquivo de suporte da plataforma. |
| [`components/control-plane/etc/systemd/system/cloudif-agent-controller.service`](../components/control-plane/etc/systemd/system/cloudif-agent-controller.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-agent-controller.timer`](../components/control-plane/etc/systemd/system/cloudif-agent-controller.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-agent-pki-crl-refresh.service`](../components/control-plane/etc/systemd/system/cloudif-agent-pki-crl-refresh.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-agent-pki-crl-refresh.timer`](../components/control-plane/etc/systemd/system/cloudif-agent-pki-crl-refresh.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-agent-registry.service`](../components/control-plane/etc/systemd/system/cloudif-agent-registry.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-approval-api.service`](../components/control-plane/etc/systemd/system/cloudif-approval-api.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-authz-gate.service`](../components/control-plane/etc/systemd/system/cloudif-authz-gate.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-authz-gate.service.d/20-cloudif-v2-access.conf`](../components/control-plane/etc/systemd/system/cloudif-authz-gate.service.d/20-cloudif-v2-access.conf) | Configuração de serviço, proxy ou aplicação. |
| [`components/control-plane/etc/systemd/system/cloudif-authz-gate.service.d/20-security.conf`](../components/control-plane/etc/systemd/system/cloudif-authz-gate.service.d/20-security.conf) | Configuração de serviço, proxy ou aplicação. |
| [`components/control-plane/etc/systemd/system/cloudif-authz-gate.service.d/README.md`](../components/control-plane/etc/systemd/system/cloudif-authz-gate.service.d/README.md) | Documentação deste diretório. |
| [`components/control-plane/etc/systemd/system/cloudif-authz-gate.service.d/override.conf`](../components/control-plane/etc/systemd/system/cloudif-authz-gate.service.d/override.conf) | Configuração de serviço, proxy ou aplicação. |
| [`components/control-plane/etc/systemd/system/cloudif-build-broker.service`](../components/control-plane/etc/systemd/system/cloudif-build-broker.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-build-worker.service`](../components/control-plane/etc/systemd/system/cloudif-build-worker.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-build-worker.service.d/README.md`](../components/control-plane/etc/systemd/system/cloudif-build-worker.service.d/README.md) | Documentação deste diretório. |
| [`components/control-plane/etc/systemd/system/cloudif-build-worker.service.d/timeout.conf`](../components/control-plane/etc/systemd/system/cloudif-build-worker.service.d/timeout.conf) | Configuração de serviço, proxy ou aplicação. |
| [`components/control-plane/etc/systemd/system/cloudif-build-worker.timer`](../components/control-plane/etc/systemd/system/cloudif-build-worker.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-certificate-alert-dispatcher.service`](../components/control-plane/etc/systemd/system/cloudif-certificate-alert-dispatcher.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-certificate-alert-dispatcher.timer`](../components/control-plane/etc/systemd/system/cloudif-certificate-alert-dispatcher.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-config-backup.service`](../components/control-plane/etc/systemd/system/cloudif-config-backup.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-config-backup.timer`](../components/control-plane/etc/systemd/system/cloudif-config-backup.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-control-dashboard.service`](../components/control-plane/etc/systemd/system/cloudif-control-dashboard.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-control-plane-api.service`](../components/control-plane/etc/systemd/system/cloudif-control-plane-api.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-control-plane-integrity.service`](../components/control-plane/etc/systemd/system/cloudif-control-plane-integrity.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-control-plane-integrity.timer`](../components/control-plane/etc/systemd/system/cloudif-control-plane-integrity.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-control-plane-smoke.service`](../components/control-plane/etc/systemd/system/cloudif-control-plane-smoke.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-control-plane-smoke.timer`](../components/control-plane/etc/systemd/system/cloudif-control-plane-smoke.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-control-plane-sync.service`](../components/control-plane/etc/systemd/system/cloudif-control-plane-sync.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-control-plane-sync.timer`](../components/control-plane/etc/systemd/system/cloudif-control-plane-sync.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-controller-certificate-renew.service`](../components/control-plane/etc/systemd/system/cloudif-controller-certificate-renew.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-controller-certificate-renew.timer`](../components/control-plane/etc/systemd/system/cloudif-controller-certificate-renew.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-data-retention.service`](../components/control-plane/etc/systemd/system/cloudif-data-retention.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-data-retention.timer`](../components/control-plane/etc/systemd/system/cloudif-data-retention.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-deploy-panel.service`](../components/control-plane/etc/systemd/system/cloudif-deploy-panel.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-deploy-panel.service.d/20-security.conf`](../components/control-plane/etc/systemd/system/cloudif-deploy-panel.service.d/20-security.conf) | Configuração de serviço, proxy ou aplicação. |
| [`components/control-plane/etc/systemd/system/cloudif-deploy-panel.service.d/README.md`](../components/control-plane/etc/systemd/system/cloudif-deploy-panel.service.d/README.md) | Documentação deste diretório. |
| [`components/control-plane/etc/systemd/system/cloudif-deployment-broker.service`](../components/control-plane/etc/systemd/system/cloudif-deployment-broker.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-deployment-broker.service.d/README.md`](../components/control-plane/etc/systemd/system/cloudif-deployment-broker.service.d/README.md) | Documentação deste diretório. |
| [`components/control-plane/etc/systemd/system/cloudif-deployment-broker.service.d/network.conf`](../components/control-plane/etc/systemd/system/cloudif-deployment-broker.service.d/network.conf) | Configuração de serviço, proxy ou aplicação. |
| [`components/control-plane/etc/systemd/system/cloudif-evaluation-api.service`](../components/control-plane/etc/systemd/system/cloudif-evaluation-api.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-firewall-8099.service`](../components/control-plane/etc/systemd/system/cloudif-firewall-8099.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-healthcheck.service`](../components/control-plane/etc/systemd/system/cloudif-healthcheck.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-healthcheck.timer`](../components/control-plane/etc/systemd/system/cloudif-healthcheck.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-input-firewall.service`](../components/control-plane/etc/systemd/system/cloudif-input-firewall.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-logrotate-verify.service`](../components/control-plane/etc/systemd/system/cloudif-logrotate-verify.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-logrotate-verify.timer`](../components/control-plane/etc/systemd/system/cloudif-logrotate-verify.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-machine-admin-db-backup.service`](../components/control-plane/etc/systemd/system/cloudif-machine-admin-db-backup.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-machine-admin-db-backup.timer`](../components/control-plane/etc/systemd/system/cloudif-machine-admin-db-backup.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-machine-admin-dr-backup.service`](../components/control-plane/etc/systemd/system/cloudif-machine-admin-dr-backup.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-machine-admin-dr-backup.timer`](../components/control-plane/etc/systemd/system/cloudif-machine-admin-dr-backup.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-machine-admin-dr-restore-test.service`](../components/control-plane/etc/systemd/system/cloudif-machine-admin-dr-restore-test.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-machine-admin-dr-restore-test.timer`](../components/control-plane/etc/systemd/system/cloudif-machine-admin-dr-restore-test.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-machine-admin-dr-restore-validation.service`](../components/control-plane/etc/systemd/system/cloudif-machine-admin-dr-restore-validation.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-machine-admin-dr-restore-validation.timer`](../components/control-plane/etc/systemd/system/cloudif-machine-admin-dr-restore-validation.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-machine-controller.service`](../components/control-plane/etc/systemd/system/cloudif-machine-controller.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-machine-guardian.service`](../components/control-plane/etc/systemd/system/cloudif-machine-guardian.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-machine-guardian.timer`](../components/control-plane/etc/systemd/system/cloudif-machine-guardian.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-machine-harvester.service`](../components/control-plane/etc/systemd/system/cloudif-machine-harvester.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-machine-harvester.timer`](../components/control-plane/etc/systemd/system/cloudif-machine-harvester.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-mcp-gateway.service`](../components/control-plane/etc/systemd/system/cloudif-mcp-gateway.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-monitor-api.service`](../components/control-plane/etc/systemd/system/cloudif-monitor-api.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-monitor-collector.service`](../components/control-plane/etc/systemd/system/cloudif-monitor-collector.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-monitor-collector.timer`](../components/control-plane/etc/systemd/system/cloudif-monitor-collector.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-monthly-restore-test.service`](../components/control-plane/etc/systemd/system/cloudif-monthly-restore-test.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-monthly-restore-test.timer`](../components/control-plane/etc/systemd/system/cloudif-monthly-restore-test.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-multiservice-preview-broker.service`](../components/control-plane/etc/systemd/system/cloudif-multiservice-preview-broker.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-node-metrics.service`](../components/control-plane/etc/systemd/system/cloudif-node-metrics.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-node-metrics.service.d/10-bind-internal.conf`](../components/control-plane/etc/systemd/system/cloudif-node-metrics.service.d/10-bind-internal.conf) | Configuração de serviço, proxy ou aplicação. |
| [`components/control-plane/etc/systemd/system/cloudif-node-metrics.service.d/20-security.conf`](../components/control-plane/etc/systemd/system/cloudif-node-metrics.service.d/20-security.conf) | Configuração de serviço, proxy ou aplicação. |
| [`components/control-plane/etc/systemd/system/cloudif-node-metrics.service.d/README.md`](../components/control-plane/etc/systemd/system/cloudif-node-metrics.service.d/README.md) | Documentação deste diretório. |
| [`components/control-plane/etc/systemd/system/cloudif-notification-api.service`](../components/control-plane/etc/systemd/system/cloudif-notification-api.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-notification-evaluator.service`](../components/control-plane/etc/systemd/system/cloudif-notification-evaluator.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-notification-evaluator.timer`](../components/control-plane/etc/systemd/system/cloudif-notification-evaluator.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-portal-qa.service`](../components/control-plane/etc/systemd/system/cloudif-portal-qa.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-portal-refresh-cache.service`](../components/control-plane/etc/systemd/system/cloudif-portal-refresh-cache.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-portal-refresh-cache.timer`](../components/control-plane/etc/systemd/system/cloudif-portal-refresh-cache.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-portal-ttl-janitor.service`](../components/control-plane/etc/systemd/system/cloudif-portal-ttl-janitor.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-portal-ttl-janitor.timer`](../components/control-plane/etc/systemd/system/cloudif-portal-ttl-janitor.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-preview-broker.service`](../components/control-plane/etc/systemd/system/cloudif-preview-broker.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-preview-cleanup.service`](../components/control-plane/etc/systemd/system/cloudif-preview-cleanup.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-preview-cleanup.timer`](../components/control-plane/etc/systemd/system/cloudif-preview-cleanup.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-prod-ui-smoke.service`](../components/control-plane/etc/systemd/system/cloudif-prod-ui-smoke.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-prod-ui-smoke.timer`](../components/control-plane/etc/systemd/system/cloudif-prod-ui-smoke.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-production-window-guard.service`](../components/control-plane/etc/systemd/system/cloudif-production-window-guard.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-production-window-guard.timer`](../components/control-plane/etc/systemd/system/cloudif-production-window-guard.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-project-backup-auto.service`](../components/control-plane/etc/systemd/system/cloudif-project-backup-auto.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-project-backup-auto.timer`](../components/control-plane/etc/systemd/system/cloudif-project-backup-auto.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-project-backup.service`](../components/control-plane/etc/systemd/system/cloudif-project-backup.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-project-backup.timer`](../components/control-plane/etc/systemd/system/cloudif-project-backup.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-project-capabilities.path`](../components/control-plane/etc/systemd/system/cloudif-project-capabilities.path) | Arquivo de suporte da plataforma. |
| [`components/control-plane/etc/systemd/system/cloudif-project-capabilities.service`](../components/control-plane/etc/systemd/system/cloudif-project-capabilities.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-project-capabilities.timer`](../components/control-plane/etc/systemd/system/cloudif-project-capabilities.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-project-config-controller.service`](../components/control-plane/etc/systemd/system/cloudif-project-config-controller.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-project-config-reconciler.service`](../components/control-plane/etc/systemd/system/cloudif-project-config-reconciler.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-project-observability.service`](../components/control-plane/etc/systemd/system/cloudif-project-observability.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-project-onboarding-reconcile.service`](../components/control-plane/etc/systemd/system/cloudif-project-onboarding-reconcile.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-project-onboarding-reconcile.timer`](../components/control-plane/etc/systemd/system/cloudif-project-onboarding-reconcile.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-project-onboarding.service`](../components/control-plane/etc/systemd/system/cloudif-project-onboarding.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-project-provision-recover.service`](../components/control-plane/etc/systemd/system/cloudif-project-provision-recover.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-project-provision-recover.timer`](../components/control-plane/etc/systemd/system/cloudif-project-provision-recover.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-project-runtime-reconciler.service`](../components/control-plane/etc/systemd/system/cloudif-project-runtime-reconciler.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-project-state-reconcile.path`](../components/control-plane/etc/systemd/system/cloudif-project-state-reconcile.path) | Arquivo de suporte da plataforma. |
| [`components/control-plane/etc/systemd/system/cloudif-project-state-reconcile.service`](../components/control-plane/etc/systemd/system/cloudif-project-state-reconcile.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-project-state-reconcile.timer`](../components/control-plane/etc/systemd/system/cloudif-project-state-reconcile.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-publication-worker.service`](../components/control-plane/etc/systemd/system/cloudif-publication-worker.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-qa-ui-smoke.service`](../components/control-plane/etc/systemd/system/cloudif-qa-ui-smoke.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-qa-ui-smoke.timer`](../components/control-plane/etc/systemd/system/cloudif-qa-ui-smoke.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-reconcile-worker.path`](../components/control-plane/etc/systemd/system/cloudif-reconcile-worker.path) | Arquivo de suporte da plataforma. |
| [`components/control-plane/etc/systemd/system/cloudif-reconcile-worker.service`](../components/control-plane/etc/systemd/system/cloudif-reconcile-worker.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-reconcile-worker.timer`](../components/control-plane/etc/systemd/system/cloudif-reconcile-worker.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-release-dispatch.service`](../components/control-plane/etc/systemd/system/cloudif-release-dispatch.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-release-dispatch.timer`](../components/control-plane/etc/systemd/system/cloudif-release-dispatch.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-runtime-policy.service`](../components/control-plane/etc/systemd/system/cloudif-runtime-policy.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-storage-guard.service`](../components/control-plane/etc/systemd/system/cloudif-storage-guard.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-storage-guard.timer`](../components/control-plane/etc/systemd/system/cloudif-storage-guard.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-supabase-launch-api.service`](../components/control-plane/etc/systemd/system/cloudif-supabase-launch-api.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-supabase-launch-api.service.d/20-security.conf`](../components/control-plane/etc/systemd/system/cloudif-supabase-launch-api.service.d/20-security.conf) | Configuração de serviço, proxy ou aplicação. |
| [`components/control-plane/etc/systemd/system/cloudif-supabase-launch-api.service.d/README.md`](../components/control-plane/etc/systemd/system/cloudif-supabase-launch-api.service.d/README.md) | Documentação deste diretório. |
| [`components/control-plane/etc/systemd/system/cloudif-supabase-mcp-broker.service`](../components/control-plane/etc/systemd/system/cloudif-supabase-mcp-broker.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-supabase-onboarding-broker.service`](../components/control-plane/etc/systemd/system/cloudif-supabase-onboarding-broker.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-supabase-release-agent.service`](../components/control-plane/etc/systemd/system/cloudif-supabase-release-agent.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-supabase-session-broker.service`](../components/control-plane/etc/systemd/system/cloudif-supabase-session-broker.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-supabase-session-broker.service.d/20-security.conf`](../components/control-plane/etc/systemd/system/cloudif-supabase-session-broker.service.d/20-security.conf) | Configuração de serviço, proxy ou aplicação. |
| [`components/control-plane/etc/systemd/system/cloudif-supabase-session-broker.service.d/30-umask.conf`](../components/control-plane/etc/systemd/system/cloudif-supabase-session-broker.service.d/30-umask.conf) | Configuração de serviço, proxy ou aplicação. |
| [`components/control-plane/etc/systemd/system/cloudif-supabase-session-broker.service.d/README.md`](../components/control-plane/etc/systemd/system/cloudif-supabase-session-broker.service.d/README.md) | Documentação deste diretório. |
| [`components/control-plane/etc/systemd/system/cloudif-tenant-certificate-reconcile.service`](../components/control-plane/etc/systemd/system/cloudif-tenant-certificate-reconcile.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-tenant-certificate-reconcile.timer`](../components/control-plane/etc/systemd/system/cloudif-tenant-certificate-reconcile.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-tenant-db-backup-v2.service`](../components/control-plane/etc/systemd/system/cloudif-tenant-db-backup-v2.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-tenant-db-backup-v2.timer`](../components/control-plane/etc/systemd/system/cloudif-tenant-db-backup-v2.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-tenant-db-backup.service`](../components/control-plane/etc/systemd/system/cloudif-tenant-db-backup.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-tenant-db-backup.timer`](../components/control-plane/etc/systemd/system/cloudif-tenant-db-backup.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-tenant-guard.service`](../components/control-plane/etc/systemd/system/cloudif-tenant-guard.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-tenant-guard.service.d/20-cloudif-v2-access.conf`](../components/control-plane/etc/systemd/system/cloudif-tenant-guard.service.d/20-cloudif-v2-access.conf) | Configuração de serviço, proxy ou aplicação. |
| [`components/control-plane/etc/systemd/system/cloudif-tenant-guard.service.d/README.md`](../components/control-plane/etc/systemd/system/cloudif-tenant-guard.service.d/README.md) | Documentação deste diretório. |
| [`components/control-plane/etc/systemd/system/cloudif-transaction-reconciler.service`](../components/control-plane/etc/systemd/system/cloudif-transaction-reconciler.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-transaction-reconciler.timer`](../components/control-plane/etc/systemd/system/cloudif-transaction-reconciler.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-ui-security-review.service`](../components/control-plane/etc/systemd/system/cloudif-ui-security-review.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-ui-security-review.timer`](../components/control-plane/etc/systemd/system/cloudif-ui-security-review.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/etc/systemd/system/cloudif-workspace-broker.service`](../components/control-plane/etc/systemd/system/cloudif-workspace-broker.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-workspace-cleanup.service`](../components/control-plane/etc/systemd/system/cloudif-workspace-cleanup.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/control-plane/etc/systemd/system/cloudif-workspace-cleanup.timer`](../components/control-plane/etc/systemd/system/cloudif-workspace-cleanup.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/control-plane/srv/README.md`](../components/control-plane/srv/README.md) | Documentação deste diretório. |
| [`components/control-plane/srv/cloudif/README.md`](../components/control-plane/srv/cloudif/README.md) | Documentação deste diretório. |
| [`components/control-plane/srv/cloudif/bin/README.md`](../components/control-plane/srv/cloudif/bin/README.md) | Documentação deste diretório. |
| [`components/control-plane/srv/cloudif/bin/cloudif-apply-router-authz-v233.sh`](../components/control-plane/srv/cloudif/bin/cloudif-apply-router-authz-v233.sh) | Script Shell que renderiza, valida ou recarrega rotas. |
| [`components/control-plane/srv/cloudif/bin/cloudif-apply-router-missing-upstream-v253.sh`](../components/control-plane/srv/cloudif/bin/cloudif-apply-router-missing-upstream-v253.sh) | Script Shell que renderiza, valida ou recarrega rotas. |
| [`components/control-plane/srv/cloudif/bin/cloudif-apply-router-portal-v1.sh`](../components/control-plane/srv/cloudif/bin/cloudif-apply-router-portal-v1.sh) | Script Shell que renderiza, valida ou recarrega rotas. |
| [`components/control-plane/srv/cloudif/bin/cloudif-auto-ensure-supabase-tenant.sh`](../components/control-plane/srv/cloudif/bin/cloudif-auto-ensure-supabase-tenant.sh) | Script Shell de criação, manutenção ou reconciliação de tenant. |
| [`components/control-plane/srv/cloudif/bin/cloudif-create-tenant.real.sh`](../components/control-plane/srv/cloudif/bin/cloudif-create-tenant.real.sh) | Script Shell de criação, manutenção ou reconciliação de tenant. |
| [`components/control-plane/srv/cloudif/bin/cloudif-create-tenant.sh`](../components/control-plane/srv/cloudif/bin/cloudif-create-tenant.sh) | Script Shell de criação, manutenção ou reconciliação de tenant. |
| [`components/control-plane/srv/cloudif/bin/cloudif-ensure-tenant-certificate.sh`](../components/control-plane/srv/cloudif/bin/cloudif-ensure-tenant-certificate.sh) | Script Shell de criação, manutenção ou reconciliação de tenant. |
| [`components/control-plane/srv/cloudif/bin/cloudif-env-set.py`](../components/control-plane/srv/cloudif/bin/cloudif-env-set.py) | Módulo Python da plataforma. |
| [`components/control-plane/srv/cloudif/bin/cloudif-fast-ensure-tenant.sh`](../components/control-plane/srv/cloudif/bin/cloudif-fast-ensure-tenant.sh) | Script Shell de criação, manutenção ou reconciliação de tenant. |
| [`components/control-plane/srv/cloudif/bin/cloudif-fix-compose-db-internal-port.sh`](../components/control-plane/srv/cloudif/bin/cloudif-fix-compose-db-internal-port.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/srv/cloudif/bin/cloudif-forja-client.py`](../components/control-plane/srv/cloudif/bin/cloudif-forja-client.py) | Implementa `read_env`, `request`, `main`. |
| [`components/control-plane/srv/cloudif/bin/cloudif-integrations-cli.py`](../components/control-plane/srv/cloudif/bin/cloudif-integrations-cli.py) | Implementa `read_env`, `bool_env`, `http_json`, `clean_base`, `repo_name`, `forgejo_status` e outros componentes. |
| [`components/control-plane/srv/cloudif/bin/cloudif-jwt.py`](../components/control-plane/srv/cloudif/bin/cloudif-jwt.py) | Implementa `b64`. |
| [`components/control-plane/srv/cloudif/bin/cloudif-patch-strict-project-entry.sh`](../components/control-plane/srv/cloudif/bin/cloudif-patch-strict-project-entry.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/srv/cloudif/bin/cloudif-project-integrate.sh`](../components/control-plane/srv/cloudif/bin/cloudif-project-integrate.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/srv/cloudif/bin/cloudif-project-orchestrator-v3.py`](../components/control-plane/srv/cloudif/bin/cloudif-project-orchestrator-v3.py) | Implementa `canonical_repo_name`, `now`, `slugify`, `run`, `read_json`, `write_json` e outros componentes. |
| [`components/control-plane/srv/cloudif/bin/cloudif-project-orchestrator-v4.py`](../components/control-plane/srv/cloudif/bin/cloudif-project-orchestrator-v4.py) | Implementa `canonical_repo_name`, `now`, `slugify`, `run`, `read_json`, `write_json` e outros componentes. |
| [`components/control-plane/srv/cloudif/bin/cloudif-render-router-sso.sh`](../components/control-plane/srv/cloudif/bin/cloudif-render-router-sso.sh) | Script Shell que renderiza, valida ou recarrega rotas. |
| [`components/control-plane/srv/cloudif/bin/cloudif-render-router.sh`](../components/control-plane/srv/cloudif/bin/cloudif-render-router.sh) | Script Shell que renderiza, valida ou recarrega rotas. |
| [`components/control-plane/srv/cloudif/bin/cloudif-sanitize-compose.sh`](../components/control-plane/srv/cloudif/bin/cloudif-sanitize-compose.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/srv/cloudif/bin/cloudif-supabase-ensure-project-hooks.sh`](../components/control-plane/srv/cloudif/bin/cloudif-supabase-ensure-project-hooks.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/srv/cloudif/bin/cloudif-supabase-ensure-user-tenant.sh`](../components/control-plane/srv/cloudif/bin/cloudif-supabase-ensure-user-tenant.sh) | Script Shell de criação, manutenção ou reconciliação de tenant. |
| [`components/control-plane/srv/cloudif/bin/cloudif-sync-db-passwords-v2.sh`](../components/control-plane/srv/cloudif/bin/cloudif-sync-db-passwords-v2.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/srv/cloudif/bin/cloudif-sync-db-passwords.sh`](../components/control-plane/srv/cloudif/bin/cloudif-sync-db-passwords.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/srv/cloudif/bin/cloudif-tenant-access-check.py`](../components/control-plane/srv/cloudif/bin/cloudif-tenant-access-check.py) | Implementa `split_csv`, `norm`, `load_env_file`, `load_access_dir`, `main`. |
| [`components/control-plane/srv/cloudif/bin/cloudif-tenant-deep-check-v2.sh`](../components/control-plane/srv/cloudif/bin/cloudif-tenant-deep-check-v2.sh) | Script Shell de criação, manutenção ou reconciliação de tenant. |
| [`components/control-plane/srv/cloudif/bin/cloudif-tenant-deep-check.sh`](../components/control-plane/srv/cloudif/bin/cloudif-tenant-deep-check.sh) | Script Shell de criação, manutenção ou reconciliação de tenant. |
| [`components/control-plane/srv/cloudif/bin/cloudif-tune-router-nginx-limits-v238.sh`](../components/control-plane/srv/cloudif/bin/cloudif-tune-router-nginx-limits-v238.sh) | Script Shell que renderiza, valida ou recarrega rotas. |
| [`components/control-plane/srv/cloudif/bin/cloudif-v2-audit.sh`](../components/control-plane/srv/cloudif/bin/cloudif-v2-audit.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/srv/cloudif/bin/cloudif-write-kong-v134.sh`](../components/control-plane/srv/cloudif/bin/cloudif-write-kong-v134.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/srv/cloudif/lib/README.md`](../components/control-plane/srv/cloudif/lib/README.md) | Documentação deste diretório. |
| [`components/control-plane/srv/cloudif/lib/cloudif-common.sh`](../components/control-plane/srv/cloudif/lib/cloudif-common.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/srv/cloudif/lib/cloudif-supabase.sh`](../components/control-plane/srv/cloudif/lib/cloudif-supabase.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/srv/cloudif/lib/cloudif_ad_directory_module.py`](../components/control-plane/srv/cloudif/lib/cloudif_ad_directory_module.py) | Implementa `_db`, `_rows`, `_tables`, `_cols`, `_pick`, `setting_value` e outros componentes. |
| [`components/control-plane/srv/cloudif/lib/cloudif_ad_search_module.py`](../components/control-plane/srv/cloudif/lib/cloudif_ad_search_module.py) | Implementa `_db`, `_rows`, `_tables`, `_cols`, `_pick`, `_setting_value` e outros componentes. |
| [`components/control-plane/srv/cloudif/lib/cloudif_admin_project_delete.py`](../components/control-plane/srv/cloudif/lib/cloudif_admin_project_delete.py) | Implementa `issue_wizard_token`, `consume_wizard_token`, `_confirmation_matches`, `_job_write`, `job_status`, `start_job` e outros componentes. |
| [`components/control-plane/srv/cloudif/lib/cloudif_admin_tenant_delete.py`](../components/control-plane/srv/cloudif/lib/cloudif_admin_tenant_delete.py) | Safe, asynchronous tenant/database deletion for CloudIFF. |
| [`components/control-plane/srv/cloudif/lib/cloudif_bancos_module.py`](../components/control-plane/srv/cloudif/lib/cloudif_bancos_module.py) | Implementa `h`, `read_env`, `db_path`, `add_tenant`, `list_tenants`, `render_bancos_style` e outros componentes. |
| [`components/control-plane/srv/cloudif/lib/cloudif_delete_git_komodo_action.py`](../components/control-plane/srv/cloudif/lib/cloudif_delete_git_komodo_action.py) | Implementa `h`, `read_env`, `db_path`, `forja_config`, `form_get`, `request_op` e outros componentes. |
| [`components/control-plane/srv/cloudif/lib/cloudif_frontend_v55.py`](../components/control-plane/srv/cloudif/lib/cloudif_frontend_v55.py) | Implementa `now`, `h`, `db`, `table_exists`, `db_one`, `db_all` e outros componentes. |
| [`components/control-plane/srv/cloudif/lib/cloudif_git_komodo_module.py`](../components/control-plane/srv/cloudif/lib/cloudif_git_komodo_module.py) | Implementa `h`, `read_env`, `refresh_public_host`, `db_rows`, `db_exec`, `table_cols` e outros componentes. |
| [`components/control-plane/srv/cloudif/lib/cloudif_machine_db.py`](../components/control-plane/srv/cloudif/lib/cloudif_machine_db.py) | Implementa `_pg_connect`, `PgConnection`, `connect`, `init_schema`, `table_columns`. |
| [`components/control-plane/srv/cloudif/lib/cloudif_multiservice_preview_portal.py`](../components/control-plane/srv/cloudif/lib/cloudif_multiservice_preview_portal.py) | Implementa `_send`, `_json`, `handle_preview_request`. |
| [`components/control-plane/srv/cloudif/lib/cloudif_onboarding_v2.py`](../components/control-plane/srv/cloudif/lib/cloudif_onboarding_v2.py) | Código inicial publicado em todo projeto novo da CloudIFF. |
| [`components/control-plane/srv/cloudif/lib/cloudif_portal_artifact_upload.py`](../components/control-plane/srv/cloudif/lib/cloudif_portal_artifact_upload.py) | Implementa `_json_body`, `ticket_status`, `artifact_status`, `project_allowed`, `safe_metadata`, `_forward_upload` e outros componentes. |
| [`components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py`](../components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py) | Implementa `_env`, `_post`, `_publication_error`, `_project_allowed`, `_ensure_schema`, `_number` e outros componentes. |
| [`components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py`](../components/control-plane/srv/cloudif/lib/cloudif_portal_v2_coexist.py) | CloudIFF Portal v2 coexistence and auto-recovery adapter |
| [`components/control-plane/srv/cloudif/lib/cloudif_project_acl_module.py`](../components/control-plane/srv/cloudif/lib/cloudif_project_acl_module.py) | Implementa `h`, `con`, `table_cols`, `pick`, `detect_acl_config`, `project_row` e outros componentes. |
| [`components/control-plane/srv/cloudif/lib/cloudif_project_action_safe.py`](../components/control-plane/srv/cloudif/lib/cloudif_project_action_safe.py) | Implementa `_log`, `h`, `slugify`, `now_stamp`, `user_from_headers`, `val` e outros componentes. |
| [`components/control-plane/srv/cloudif/lib/cloudif_project_config_events.py`](../components/control-plane/srv/cloudif/lib/cloudif_project_config_events.py) | Implementa `_env`, `_safe_details`, `event_for_reconcile`, `notify`. |
| [`components/control-plane/srv/cloudif/lib/cloudif_project_environment_web.py`](../components/control-plane/srv/cloudif/lib/cloudif_project_environment_web.py) | Implementa `_env_file_value`, `_json_call`, `_control_project`, `authorization`, `_config_path`, `_config` e outros componentes. |
| [`components/control-plane/srv/cloudif/lib/cloudif_project_environments_overview.py`](../components/control-plane/srv/cloudif/lib/cloudif_project_environments_overview.py) | Implementa `_config`, `_runtime`, `_preview`, `_production`, `overview`, `handle_get`. |
| [`components/control-plane/srv/cloudif/lib/cloudif_project_observability_web.py`](../components/control-plane/srv/cloudif/lib/cloudif_project_observability_web.py) | Implementa `_call`, `handle_get`. |
| [`components/control-plane/srv/cloudif/lib/cloudif_project_provision_real.py`](../components/control-plane/srv/cloudif/lib/cloudif_project_provision_real.py) | Implementa `log`, `load_env_files`, `env`, `slugify`, `run`, `http_json` e outros componentes. |
| [`components/control-plane/srv/cloudif/lib/cloudif_project_provision_recover.py`](../components/control-plane/srv/cloudif/lib/cloudif_project_provision_recover.py) | Implementa `unit_name`, `parse_time`, `active`, `launch`, `main`. |
| [`components/control-plane/srv/cloudif/lib/cloudif_project_provision_status.py`](../components/control-plane/srv/cloudif/lib/cloudif_project_provision_status.py) | Implementa `_load`, `_connect`, `_project`, `_publication`, `_public_number`, `_jobs` e outros componentes. |
| [`components/control-plane/srv/cloudif/lib/cloudif_project_provision_worker.py`](../components/control-plane/srv/cloudif/lib/cloudif_project_provision_worker.py) | Implementa `log`, `atomic_job`, `set_state`, `run`, `json_output`, `require_timer` e outros componentes. |
| [`components/control-plane/srv/cloudif/lib/cloudif_project_publication_config.py`](../components/control-plane/srv/cloudif/lib/cloudif_project_publication_config.py) | Implementa `_env`, `_json`, `_config_headers`, `_komodo_headers`, `_environment_name`, `_effective` e outros componentes. |
| [`components/control-plane/srv/cloudif/lib/cloudif_project_runtime_reconcile_web.py`](../components/control-plane/srv/cloudif/lib/cloudif_project_runtime_reconcile_web.py) | Implementa `_call`, `handle_get`, `handle_post`. |
| [`components/control-plane/srv/cloudif/lib/cloudif_project_secret_web.py`](../components/control-plane/srv/cloudif/lib/cloudif_project_secret_web.py) | Implementa `_config`, `_plan`, `_require_read`, `_require_write`, `_require_secret_read`, `_approval_metadata` e outros componentes. |
| [`components/control-plane/srv/cloudif/lib/cloudif_project_toolchain_web.py`](../components/control-plane/srv/cloudif/lib/cloudif_project_toolchain_web.py) | Implementa `_build`, `_require_write`, `_plan`, `_activation_plan`, `_create_approval`, `request_build_approval` e outros componentes. |
| [`components/control-plane/srv/cloudif/lib/cloudif_publish_site_action.py`](../components/control-plane/srv/cloudif/lib/cloudif_publish_site_action.py) | Implementa `_read_env`, `_komodo_agent_config`, `_form_get`, `_http_post_json`, `_is_publish_op`, `handle_publish_site_action`. |
| [`components/control-plane/srv/cloudif/lib/cloudif_rbac.py`](../components/control-plane/srv/cloudif/lib/cloudif_rbac.py) | Implementa `_groups`, `_identities`, `is_global_admin`, `_level`, `_project_level`, `_tenant_level` e outros componentes. |
| [`components/control-plane/srv/cloudif/lib/cloudif_reconcile_client.py`](../components/control-plane/srv/cloudif/lib/cloudif_reconcile_client.py) | Implementa `now_utc`, `connect`, `ensure_schema`, `_safe_slug`, `_contains_secret`, `_partition` e outros componentes. |
| [`components/control-plane/srv/cloudif/lib/cloudif_release_manager.py`](../components/control-plane/srv/cloudif/lib/cloudif_release_manager.py) | Implementa `now_utc`, `parse_utc`, `read_env`, `connect`, `ensure_schema`, `safe_detail` e outros componentes. |
| [`components/control-plane/srv/cloudif/lib/cloudif_theme_module.py`](../components/control-plane/srv/cloudif/lib/cloudif_theme_module.py) | Implementa `render_theme_css`. |
| [`components/control-plane/srv/cloudif/lib/cloudif_ui_components.py`](../components/control-plane/srv/cloudif/lib/cloudif_ui_components.py) | Implementa `h`, `css`, `btn`, `pill`, `menu_tabs`, `banner` e outros componentes. |
| [`components/control-plane/srv/cloudif/lib/cloudif_ui_data.py`](../components/control-plane/srv/cloudif/lib/cloudif_ui_data.py) | Implementa `db_rows`, `discover_projects`, `discover_tenants`, `public_studio_url`, `deploy_url`, `tab_url` e outros componentes. |
| [`components/control-plane/srv/cloudif/lib/cloudif_ui_modular.py`](../components/control-plane/srv/cloudif/lib/cloudif_ui_modular.py) | Módulo Python da plataforma. |
| [`components/control-plane/srv/cloudif/lib/cloudif_ui_pages.py`](../components/control-plane/srv/cloudif/lib/cloudif_ui_pages.py) | Implementa `_v95_user_name`, `_v95_user_groups`, `_v95_is_admin`, `_v95_tenant_name`, `_v95_allowed_tenants`, `_v95_options` e outros componentes. |
| [`components/control-plane/srv/cloudif/lib/cloudif_ui_publications.py`](../components/control-plane/srv/cloudif/lib/cloudif_ui_publications.py) | Implementa `h`, `_rows`, `_runtime_from_job`, `_komodo_web_status`, `_project_context`, `_project_information` e outros componentes. |
| [`components/control-plane/srv/cloudif/lib/sitecustomize.py`](../components/control-plane/srv/cloudif/lib/sitecustomize.py) | Portal-scoped startup hook |
| [`components/control-plane/srv/cloudif/router/README.md`](../components/control-plane/srv/cloudif/router/README.md) | Documentação deste diretório. |
| [`components/control-plane/srv/cloudif/router/conf.d/README.md`](../components/control-plane/srv/cloudif/router/conf.d/README.md) | Documentação deste diretório. |
| [`components/control-plane/srv/cloudif/router/conf.d/default.conf`](../components/control-plane/srv/cloudif/router/conf.d/default.conf) | Configuração de serviço, proxy ou aplicação. |
| [`components/control-plane/srv/cloudif/router/conf.d/default.conf.quebrado-v220-2026-06-04-203507`](../components/control-plane/srv/cloudif/router/conf.d/default.conf.quebrado-v220-2026-06-04-203507) | Arquivo de suporte da plataforma. |
| [`components/control-plane/srv/cloudif/router/docker-compose.yml`](../components/control-plane/srv/cloudif/router/docker-compose.yml) | Definição declarativa de serviços Docker Compose. |
| [`components/control-plane/srv/cloudif/staging/README.md`](../components/control-plane/srv/cloudif/staging/README.md) | Documentação deste diretório. |
| [`components/control-plane/srv/cloudif/staging/cloudif-admin-portal-staging.py`](../components/control-plane/srv/cloudif/staging/cloudif-admin-portal-staging.py) | Implementa `now_iso`, `h`, `norm`, `slugify`, `parse_groups`, `db` e outros componentes. |
| [`components/control-plane/srv/cloudif/staging/lib/README.md`](../components/control-plane/srv/cloudif/staging/lib/README.md) | Documentação deste diretório. |
| [`components/control-plane/srv/cloudif/staging/lib/cloudif-common.sh`](../components/control-plane/srv/cloudif/staging/lib/cloudif-common.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/srv/cloudif/staging/lib/cloudif-supabase.sh`](../components/control-plane/srv/cloudif/staging/lib/cloudif-supabase.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/srv/cloudif/staging/lib/cloudif_ad_directory_module.py`](../components/control-plane/srv/cloudif/staging/lib/cloudif_ad_directory_module.py) | Implementa `_db`, `_rows`, `_tables`, `_cols`, `_pick`, `setting_value` e outros componentes. |
| [`components/control-plane/srv/cloudif/staging/lib/cloudif_ad_search_module.py`](../components/control-plane/srv/cloudif/staging/lib/cloudif_ad_search_module.py) | Implementa `_db`, `_rows`, `_tables`, `_cols`, `_pick`, `_setting_value` e outros componentes. |
| [`components/control-plane/srv/cloudif/staging/lib/cloudif_bancos_module.py`](../components/control-plane/srv/cloudif/staging/lib/cloudif_bancos_module.py) | Implementa `h`, `read_env`, `db_path`, `add_tenant`, `list_tenants`, `render_bancos_style` e outros componentes. |
| [`components/control-plane/srv/cloudif/staging/lib/cloudif_delete_git_komodo_action.py`](../components/control-plane/srv/cloudif/staging/lib/cloudif_delete_git_komodo_action.py) | Implementa `h`, `read_env`, `db_path`, `forja_config`, `form_get`, `request_op` e outros componentes. |
| [`components/control-plane/srv/cloudif/staging/lib/cloudif_frontend_v55.py`](../components/control-plane/srv/cloudif/staging/lib/cloudif_frontend_v55.py) | Implementa `now`, `h`, `db`, `table_exists`, `db_one`, `db_all` e outros componentes. |
| [`components/control-plane/srv/cloudif/staging/lib/cloudif_git_komodo_module.py`](../components/control-plane/srv/cloudif/staging/lib/cloudif_git_komodo_module.py) | Implementa `h`, `read_env`, `refresh_public_host`, `db_rows`, `db_exec`, `table_cols` e outros componentes. |
| [`components/control-plane/srv/cloudif/staging/lib/cloudif_machine_db.py`](../components/control-plane/srv/cloudif/staging/lib/cloudif_machine_db.py) | Implementa `_pg_connect`, `PgConnection`, `connect`, `init_schema`, `table_columns`. |
| [`components/control-plane/srv/cloudif/staging/lib/cloudif_onboarding_v2.py`](../components/control-plane/srv/cloudif/staging/lib/cloudif_onboarding_v2.py) | Implementa `build_onboarding_v2`. |
| [`components/control-plane/srv/cloudif/staging/lib/cloudif_portal_publications.py`](../components/control-plane/srv/cloudif/staging/lib/cloudif_portal_publications.py) | Implementa `_env`, `_post`, `_project_allowed`, `_ensure_schema`, `_number`, `_clients` e outros componentes. |
| [`components/control-plane/srv/cloudif/staging/lib/cloudif_project_acl_module.py`](../components/control-plane/srv/cloudif/staging/lib/cloudif_project_acl_module.py) | Implementa `h`, `con`, `table_cols`, `pick`, `detect_acl_config`, `project_row` e outros componentes. |
| [`components/control-plane/srv/cloudif/staging/lib/cloudif_project_action_safe.py`](../components/control-plane/srv/cloudif/staging/lib/cloudif_project_action_safe.py) | Implementa `_log`, `h`, `slugify`, `now_stamp`, `user_from_headers`, `val` e outros componentes. |
| [`components/control-plane/srv/cloudif/staging/lib/cloudif_project_provision_real.py`](../components/control-plane/srv/cloudif/staging/lib/cloudif_project_provision_real.py) | Implementa `log`, `load_env_files`, `env`, `slugify`, `run`, `http_json` e outros componentes. |
| [`components/control-plane/srv/cloudif/staging/lib/cloudif_project_provision_worker.py`](../components/control-plane/srv/cloudif/staging/lib/cloudif_project_provision_worker.py) | Implementa `log`, `run`, `main`. |
| [`components/control-plane/srv/cloudif/staging/lib/cloudif_publish_site_action.py`](../components/control-plane/srv/cloudif/staging/lib/cloudif_publish_site_action.py) | Implementa `_read_env`, `_komodo_agent_config`, `_form_get`, `_http_post_json`, `_is_publish_op`, `handle_publish_site_action`. |
| [`components/control-plane/srv/cloudif/staging/lib/cloudif_rbac.py`](../components/control-plane/srv/cloudif/staging/lib/cloudif_rbac.py) | Implementa `_groups`, `_identities`, `is_global_admin`, `_level`, `_project_level`, `_tenant_level` e outros componentes. |
| [`components/control-plane/srv/cloudif/staging/lib/cloudif_reconcile_client.py`](../components/control-plane/srv/cloudif/staging/lib/cloudif_reconcile_client.py) | Implementa `now_utc`, `connect`, `ensure_schema`, `_safe_slug`, `enqueue`, `status` e outros componentes. |
| [`components/control-plane/srv/cloudif/staging/lib/cloudif_release_manager.py`](../components/control-plane/srv/cloudif/staging/lib/cloudif_release_manager.py) | Implementa `now_utc`, `parse_utc`, `read_env`, `connect`, `ensure_schema`, `safe_detail` e outros componentes. |
| [`components/control-plane/srv/cloudif/staging/lib/cloudif_theme_module.py`](../components/control-plane/srv/cloudif/staging/lib/cloudif_theme_module.py) | Implementa `render_theme_css`. |
| [`components/control-plane/srv/cloudif/staging/lib/cloudif_ui_components.py`](../components/control-plane/srv/cloudif/staging/lib/cloudif_ui_components.py) | Implementa `h`, `css`, `btn`, `pill`, `menu_tabs`, `banner` e outros componentes. |
| [`components/control-plane/srv/cloudif/staging/lib/cloudif_ui_data.py`](../components/control-plane/srv/cloudif/staging/lib/cloudif_ui_data.py) | Implementa `db_rows`, `discover_projects`, `discover_tenants`, `public_studio_url`, `deploy_url`, `tab_url` e outros componentes. |
| [`components/control-plane/srv/cloudif/staging/lib/cloudif_ui_modular.py`](../components/control-plane/srv/cloudif/staging/lib/cloudif_ui_modular.py) | Módulo Python da plataforma. |
| [`components/control-plane/srv/cloudif/staging/lib/cloudif_ui_pages.py`](../components/control-plane/srv/cloudif/staging/lib/cloudif_ui_pages.py) | Implementa `_v95_user_name`, `_v95_user_groups`, `_v95_is_admin`, `_v95_tenant_name`, `_v95_allowed_tenants`, `_v95_options` e outros componentes. |
| [`components/control-plane/srv/cloudif/staging/lib/cloudif_ui_publications.py`](../components/control-plane/srv/cloudif/staging/lib/cloudif_ui_publications.py) | Implementa `h`, `_rows`, `publication_panel`, `admin_publications`. |
| [`components/control-plane/srv/cloudif/tests/README.md`](../components/control-plane/srv/cloudif/tests/README.md) | Documentação deste diretório. |
| [`components/control-plane/srv/cloudif/tests/cloudif-secure-release-gate.sh`](../components/control-plane/srv/cloudif/tests/cloudif-secure-release-gate.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/srv/cloudif/tests/cloudif-ui-security-smoke.sh`](../components/control-plane/srv/cloudif/tests/cloudif-ui-security-smoke.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/srv/cloudif/tests/cloudif-ui-security-tests.py`](../components/control-plane/srv/cloudif/tests/cloudif-ui-security-tests.py) | Implementa `fetch`, `ok`. |
| [`components/control-plane/usr/README.md`](../components/control-plane/usr/README.md) | Documentação deste diretório. |
| [`components/control-plane/usr/local/README.md`](../components/control-plane/usr/local/README.md) | Documentação deste diretório. |
| [`components/control-plane/usr/local/sbin/README.md`](../components/control-plane/usr/local/sbin/README.md) | Documentação deste diretório. |
| [`components/control-plane/usr/local/sbin/cloudif-admin-portal.py`](../components/control-plane/usr/local/sbin/cloudif-admin-portal.py) | Implementa `now_iso`, `h`, `norm`, `slugify`, `parse_groups`, `db` e outros componentes. |
| [`components/control-plane/usr/local/sbin/cloudif-agent-pki.py`](../components/control-plane/usr/local/sbin/cloudif-agent-pki.py) | Implementa `now`, `run`, `audit`, `refresh_crls`, `create_token`, `enroll` e outros componentes. |
| [`components/control-plane/usr/local/sbin/cloudif-authz-gate.py`](../components/control-plane/usr/local/sbin/cloudif-authz-gate.py) | Implementa `NoRedirect`, `clean_host`, `tenant_from_request`, `groups_to_set`, `load_tenant_access`, `authorize_tenant` e outros componentes. |
| [`components/control-plane/usr/local/sbin/cloudif-certificate-alert-dispatcher.py`](../components/control-plane/usr/local/sbin/cloudif-certificate-alert-dispatcher.py) | Implementa `utcnow`, `iso`, `parse`, `env`, `should_dispatch`, `main`. |
| [`components/control-plane/usr/local/sbin/cloudif-config-backup.sh`](../components/control-plane/usr/local/sbin/cloudif-config-backup.sh) | Script Shell de backup, retenção ou sincronização. |
| [`components/control-plane/usr/local/sbin/cloudif-control-plane-api.py`](../components/control-plane/usr/local/sbin/cloudif-control-plane-api.py) | Implementa `rows`, `H`. |
| [`components/control-plane/usr/local/sbin/cloudif-control-plane-integrity.py`](../components/control-plane/usr/local/sbin/cloudif-control-plane-integrity.py) | Implementa `now`, `digest`, `metadata`, `generate`, `check`. |
| [`components/control-plane/usr/local/sbin/cloudif-control-plane-smoke.py`](../components/control-plane/usr/local/sbin/cloudif-control-plane-smoke.py) | Implementa `env`, `http`. |
| [`components/control-plane/usr/local/sbin/cloudif-control-plane-sync.py`](../components/control-plane/usr/local/sbin/cloudif-control-plane-sync.py) | Módulo Python da plataforma. |
| [`components/control-plane/usr/local/sbin/cloudif-controller-certificate-renew.sh`](../components/control-plane/usr/local/sbin/cloudif-controller-certificate-renew.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/usr/local/sbin/cloudif-data-retention.py`](../components/control-plane/usr/local/sbin/cloudif-data-retention.py) | Implementa `clean_db`, `protected_clients`, `cleanup_temp_clients`. |
| [`components/control-plane/usr/local/sbin/cloudif-deploy-panel.py`](../components/control-plane/usr/local/sbin/cloudif-deploy-panel.py) | Implementa `now`, `ensure_db`, `db_exec`, `db_one`, `db_all`, `h` e outros componentes. |
| [`components/control-plane/usr/local/sbin/cloudif-firewall-8099.sh`](../components/control-plane/usr/local/sbin/cloudif-firewall-8099.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/usr/local/sbin/cloudif-harden-router-8099.sh`](../components/control-plane/usr/local/sbin/cloudif-harden-router-8099.sh) | Script Shell que renderiza, valida ou recarrega rotas. |
| [`components/control-plane/usr/local/sbin/cloudif-healthcheck.sh`](../components/control-plane/usr/local/sbin/cloudif-healthcheck.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/usr/local/sbin/cloudif-input-firewall.sh`](../components/control-plane/usr/local/sbin/cloudif-input-firewall.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/usr/local/sbin/cloudif-inventario-oficial.sh`](../components/control-plane/usr/local/sbin/cloudif-inventario-oficial.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/usr/local/sbin/cloudif-logrotate-verify.sh`](../components/control-plane/usr/local/sbin/cloudif-logrotate-verify.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/usr/local/sbin/cloudif-machine-admin-db-backup.sh`](../components/control-plane/usr/local/sbin/cloudif-machine-admin-db-backup.sh) | Script Shell de backup, retenção ou sincronização. |
| [`components/control-plane/usr/local/sbin/cloudif-machine-admin-dr-backup.sh`](../components/control-plane/usr/local/sbin/cloudif-machine-admin-dr-backup.sh) | Script Shell de backup, retenção ou sincronização. |
| [`components/control-plane/usr/local/sbin/cloudif-machine-admin-dr-restore-test.sh`](../components/control-plane/usr/local/sbin/cloudif-machine-admin-dr-restore-test.sh) | Script Shell de restauração ou teste de recuperação. |
| [`components/control-plane/usr/local/sbin/cloudif-machine-admin-dr-restore-validation.sh`](../components/control-plane/usr/local/sbin/cloudif-machine-admin-dr-restore-validation.sh) | Script Shell de restauração ou teste de recuperação. |
| [`components/control-plane/usr/local/sbin/cloudif-machine-controller.py`](../components/control-plane/usr/local/sbin/cloudif-machine-controller.py) | Implementa `now`, `con`, `init`, `verify`, `process_certificates`, `upsert_inventory` e outros componentes. |
| [`components/control-plane/usr/local/sbin/cloudif-machine-executor.py`](../components/control-plane/usr/local/sbin/cloudif-machine-executor.py) | Módulo Python da plataforma. |
| [`components/control-plane/usr/local/sbin/cloudif-machine-guardian.py`](../components/control-plane/usr/local/sbin/cloudif-machine-guardian.py) | Implementa `send`, `main`. |
| [`components/control-plane/usr/local/sbin/cloudif-machine-harvester.py`](../components/control-plane/usr/local/sbin/cloudif-machine-harvester.py) | Implementa `verify_policy_envelope`, `controller_open`, `run`, `ensure_identity`, `cert_state`, `cert_record` e outros componentes. |
| [`components/control-plane/usr/local/sbin/cloudif-monthly-restore-test.sh`](../components/control-plane/usr/local/sbin/cloudif-monthly-restore-test.sh) | Script Shell de restauração ou teste de recuperação. |
| [`components/control-plane/usr/local/sbin/cloudif-node-metrics.py`](../components/control-plane/usr/local/sbin/cloudif-node-metrics.py) | Implementa `run`, `network_summary`, `docker_summary`, `metrics`, `H`. |
| [`components/control-plane/usr/local/sbin/cloudif-patch-async-launch-route.sh`](../components/control-plane/usr/local/sbin/cloudif-patch-async-launch-route.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/usr/local/sbin/cloudif-patch-launch-route-v2.sh`](../components/control-plane/usr/local/sbin/cloudif-patch-launch-route-v2.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/usr/local/sbin/cloudif-patch-launch-route.sh`](../components/control-plane/usr/local/sbin/cloudif-patch-launch-route.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/usr/local/sbin/cloudif-patch-supabase-root-api.sh`](../components/control-plane/usr/local/sbin/cloudif-patch-supabase-root-api.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/usr/local/sbin/cloudif-patch-supabase-router.sh`](../components/control-plane/usr/local/sbin/cloudif-patch-supabase-router.sh) | Script Shell que renderiza, valida ou recarrega rotas. |
| [`components/control-plane/usr/local/sbin/cloudif-portal-refresh-cache.py`](../components/control-plane/usr/local/sbin/cloudif-portal-refresh-cache.py) | Implementa `now_iso`, `db`, `init_db`, `fetch_json`, `network_rate`, `refresh_nodes` e outros componentes. |
| [`components/control-plane/usr/local/sbin/cloudif-portal-ttl-janitor.py`](../components/control-plane/usr/local/sbin/cloudif-portal-ttl-janitor.py) | Implementa `now`, `run`, `main`. |
| [`components/control-plane/usr/local/sbin/cloudif-project-backup-auto.py`](../components/control-plane/usr/local/sbin/cloudif-project-backup-auto.py) | Módulo Python da plataforma. |
| [`components/control-plane/usr/local/sbin/cloudif-project-backup-sync.sh`](../components/control-plane/usr/local/sbin/cloudif-project-backup-sync.sh) | Script Shell de backup, retenção ou sincronização. |
| [`components/control-plane/usr/local/sbin/cloudif-project-backup.py`](../components/control-plane/usr/local/sbin/cloudif-project-backup.py) | Implementa `now`, `stamp`, `safe`, `load_state`, `save_state`, `db_rows` e outros componentes. |
| [`components/control-plane/usr/local/sbin/cloudif-project-ensure.py`](../components/control-plane/usr/local/sbin/cloudif-project-ensure.py) | Implementa `load_env_file`, `now`, `db`, `http_json`, `audit`, `save_project` e outros componentes. |
| [`components/control-plane/usr/local/sbin/cloudif-project-initial-publish.py`](../components/control-plane/usr/local/sbin/cloudif-project-initial-publish.py) | Implementa `envfile`, `request`, `public_number`, `next_recorded_deploy_number`, `immutable_deploy_conflict`, `project_access` e outros componentes. |
| [`components/control-plane/usr/local/sbin/cloudif-project-provision.sh`](../components/control-plane/usr/local/sbin/cloudif-project-provision.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/usr/local/sbin/cloudif-project-template-apply.py`](../components/control-plane/usr/local/sbin/cloudif-project-template-apply.py) | Implementa `read_env`, `post`, `public_number`, `build`, `project_readme`, `runtime_overlay` e outros componentes. |
| [`components/control-plane/usr/local/sbin/cloudif-project-template-seed.py`](../components/control-plane/usr/local/sbin/cloudif-project-template-seed.py) | Implementa `load_env`, `req`, `svg`, `files_for`, `seed_db`, `main`. |
| [`components/control-plane/usr/local/sbin/cloudif-publication-worker.py`](../components/control-plane/usr/local/sbin/cloudif-publication-worker.py) | Implementa `stop`. |
| [`components/control-plane/usr/local/sbin/cloudif-publish-1009-once.py`](../components/control-plane/usr/local/sbin/cloudif-publish-1009-once.py) | Módulo Python da plataforma. |
| [`components/control-plane/usr/local/sbin/cloudif-reconcile-tenant-certificates.py`](../components/control-plane/usr/local/sbin/cloudif-reconcile-tenant-certificates.py) | Implementa `tenants`, `main`. |
| [`components/control-plane/usr/local/sbin/cloudif-reconcile-worker.py`](../components/control-plane/usr/local/sbin/cloudif-reconcile-worker.py) | Implementa `read_env`, `forja_project`, `reconcile_project_runtime`, `db_container`, `internal_post`, `project_membership_snapshot` e outros componentes. |
| [`components/control-plane/usr/local/sbin/cloudif-refresh-komodo-status-cache.py`](../components/control-plane/usr/local/sbin/cloudif-refresh-komodo-status-cache.py) | Implementa `now_iso`, `add_seconds_iso`, `read_env`, `komodo_agent_config`, `http_json`, `ensure_table` e outros componentes. |
| [`components/control-plane/usr/local/sbin/cloudif-release-cycle`](../components/control-plane/usr/local/sbin/cloudif-release-cycle) | Arquivo de suporte da plataforma. |
| [`components/control-plane/usr/local/sbin/cloudif-release-dispatch.py`](../components/control-plane/usr/local/sbin/cloudif-release-dispatch.py) | Implementa `main`. |
| [`components/control-plane/usr/local/sbin/cloudif-release-maintenance`](../components/control-plane/usr/local/sbin/cloudif-release-maintenance) | Arquivo de suporte da plataforma. |
| [`components/control-plane/usr/local/sbin/cloudif-requeue-project-provision.sh`](../components/control-plane/usr/local/sbin/cloudif-requeue-project-provision.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/usr/local/sbin/cloudif-secure-release-gate.sh`](../components/control-plane/usr/local/sbin/cloudif-secure-release-gate.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/usr/local/sbin/cloudif-storage-guard.py`](../components/control-plane/usr/local/sbin/cloudif-storage-guard.py) | Implementa `usage`. |
| [`components/control-plane/usr/local/sbin/cloudif-supabase-launch-api.py`](../components/control-plane/usr/local/sbin/cloudif-supabase-launch-api.py) | Implementa `now`, `public_url`, `project_url`, `unit_name`, `state_file`, `log_file` e outros componentes. |
| [`components/control-plane/usr/local/sbin/cloudif-supabase-release-agent.py`](../components/control-plane/usr/local/sbin/cloudif-supabase-release-agent.py) | Implementa `authorized`, `safe_payload`, `validate_identity`, `inspect_tenant`, `backup`, `migrate` e outros componentes. |
| [`components/control-plane/usr/local/sbin/cloudif-supabase-session-broker.py`](../components/control-plane/usr/local/sbin/cloudif-supabase-session-broker.py) | Implementa `env`, `log`, `b64url`, `fetch_json`, `discovery`, `token_request` e outros componentes. |
| [`components/control-plane/usr/local/sbin/cloudif-tenant-db-backup-v2.sh`](../components/control-plane/usr/local/sbin/cloudif-tenant-db-backup-v2.sh) | Script Shell de backup, retenção ou sincronização. |
| [`components/control-plane/usr/local/sbin/cloudif-tenant-db-backup.sh`](../components/control-plane/usr/local/sbin/cloudif-tenant-db-backup.sh) | Script Shell de backup, retenção ou sincronização. |
| [`components/control-plane/usr/local/sbin/cloudif-tenant-ensure-bg.sh`](../components/control-plane/usr/local/sbin/cloudif-tenant-ensure-bg.sh) | Script Shell de criação, manutenção ou reconciliação de tenant. |
| [`components/control-plane/usr/local/sbin/cloudif-tenant-guard.py`](../components/control-plane/usr/local/sbin/cloudif-tenant-guard.py) | Implementa `NoRedirect`, `log`, `clean_host`, `valid_tenant`, `tenant_from_request`, `env_value` e outros componentes. |
| [`components/control-plane/usr/local/sbin/cloudif-tenant-policy-ensure.py`](../components/control-plane/usr/local/sbin/cloudif-tenant-policy-ensure.py) | Apply and verify the initial availability policy of a newly-created tenant. |
| [`components/control-plane/usr/local/sbin/cloudif-test-cross-subdomain-publish-once.py`](../components/control-plane/usr/local/sbin/cloudif-test-cross-subdomain-publish-once.py) | Implementa `NR`. |
| [`components/control-plane/usr/local/sbin/cloudif-test-d2-deploy.sh`](../components/control-plane/usr/local/sbin/cloudif-test-d2-deploy.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/usr/local/sbin/cloudif-test-mobile-null-origin-publish-once.py`](../components/control-plane/usr/local/sbin/cloudif-test-mobile-null-origin-publish-once.py) | Implementa `NR`. |
| [`components/control-plane/usr/local/sbin/cloudif-test-publication-redirect-once.py`](../components/control-plane/usr/local/sbin/cloudif-test-publication-redirect-once.py) | Implementa `NoRedirect`. |
| [`components/control-plane/usr/local/sbin/cloudif-test-tenant-control-publish-once.py`](../components/control-plane/usr/local/sbin/cloudif-test-tenant-control-publish-once.py) | Implementa `NR`. |
| [`components/control-plane/usr/local/sbin/cloudif-test-tenant-publish-button-once.py`](../components/control-plane/usr/local/sbin/cloudif-test-tenant-publish-button-once.py) | Módulo Python da plataforma. |
| [`components/control-plane/usr/local/sbin/cloudif-ui-security-review-run.sh`](../components/control-plane/usr/local/sbin/cloudif-ui-security-review-run.sh) | Automação Shell operacional da plataforma. |
| [`components/control-plane/usr/local/sbin/cloudif-workspace-cleanup.py`](../components/control-plane/usr/local/sbin/cloudif-workspace-cleanup.py) | Implementa `atomic_write`, `docker`, `main`. |
| [`components/proxy/README.md`](../components/proxy/README.md) | Documentação deste diretório. |
| [`components/proxy/current-apps/README.md`](../components/proxy/current-apps/README.md) | Documentação deste diretório. |
| [`components/proxy/current-apps/access-telemetry-current/README.md`](../components/proxy/current-apps/access-telemetry-current/README.md) | Documentação deste diretório. |
| [`components/proxy/current-apps/access-telemetry-current/cloudif-access-api.py`](../components/proxy/current-apps/access-telemetry-current/cloudif-access-api.py) | Implementa `q`, `H`. |
| [`components/proxy/current-apps/access-telemetry-current/cloudif-access-collector.py`](../components/proxy/current-apps/access-telemetry-current/cloudif-access-collector.py) | Implementa `conn`, `init`, `route_of`, `client_class`, `source_of`, `parse_ts` e outros componentes. |
| [`components/proxy/current-apps/access-telemetry-current/cloudif-access-push.py`](../components/proxy/current-apps/access-telemetry-current/cloudif-access-push.py) | Implementa `q`. |
| [`components/proxy/current-apps/publisher-agent-current/README.md`](../components/proxy/current-apps/publisher-agent-current/README.md) | Documentação deste diretório. |
| [`components/proxy/current-apps/publisher-agent-current/cloudif-npm-publisher-agent.py`](../components/proxy/current-apps/publisher-agent-current/cloudif-npm-publisher-agent.py) | Implementa `env`, `load_state`, `save_state`, `run`, `cert_exists`, `cert_covers` e outros componentes. |
| [`components/proxy/etc/README.md`](../components/proxy/etc/README.md) | Documentação deste diretório. |
| [`components/proxy/etc/systemd/README.md`](../components/proxy/etc/systemd/README.md) | Documentação deste diretório. |
| [`components/proxy/etc/systemd/system/README.md`](../components/proxy/etc/systemd/system/README.md) | Documentação deste diretório. |
| [`components/proxy/etc/systemd/system/cloudif-access-api.service`](../components/proxy/etc/systemd/system/cloudif-access-api.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/proxy/etc/systemd/system/cloudif-access-collector.service`](../components/proxy/etc/systemd/system/cloudif-access-collector.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/proxy/etc/systemd/system/cloudif-access-collector.timer`](../components/proxy/etc/systemd/system/cloudif-access-collector.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/proxy/etc/systemd/system/cloudif-access-push.service`](../components/proxy/etc/systemd/system/cloudif-access-push.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/proxy/etc/systemd/system/cloudif-access-push.service.d/README.md`](../components/proxy/etc/systemd/system/cloudif-access-push.service.d/README.md) | Documentação deste diretório. |
| [`components/proxy/etc/systemd/system/cloudif-access-push.service.d/storage-compat.conf`](../components/proxy/etc/systemd/system/cloudif-access-push.service.d/storage-compat.conf) | Configuração de serviço, proxy ou aplicação. |
| [`components/proxy/etc/systemd/system/cloudif-access-push.timer`](../components/proxy/etc/systemd/system/cloudif-access-push.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/proxy/etc/systemd/system/cloudif-admin-cert-renew.service`](../components/proxy/etc/systemd/system/cloudif-admin-cert-renew.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/proxy/etc/systemd/system/cloudif-admin-cert-renew.timer`](../components/proxy/etc/systemd/system/cloudif-admin-cert-renew.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/proxy/etc/systemd/system/cloudif-machine-certificate-renew.service`](../components/proxy/etc/systemd/system/cloudif-machine-certificate-renew.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/proxy/etc/systemd/system/cloudif-machine-certificate-renew.timer`](../components/proxy/etc/systemd/system/cloudif-machine-certificate-renew.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/proxy/etc/systemd/system/cloudif-machine-guardian.service`](../components/proxy/etc/systemd/system/cloudif-machine-guardian.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/proxy/etc/systemd/system/cloudif-machine-guardian.timer`](../components/proxy/etc/systemd/system/cloudif-machine-guardian.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/proxy/etc/systemd/system/cloudif-machine-harvester.service`](../components/proxy/etc/systemd/system/cloudif-machine-harvester.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/proxy/etc/systemd/system/cloudif-machine-harvester.timer`](../components/proxy/etc/systemd/system/cloudif-machine-harvester.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/proxy/etc/systemd/system/cloudif-node-metrics.service`](../components/proxy/etc/systemd/system/cloudif-node-metrics.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/proxy/etc/systemd/system/cloudif-npm-backup.service`](../components/proxy/etc/systemd/system/cloudif-npm-backup.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/proxy/etc/systemd/system/cloudif-npm-backup.timer`](../components/proxy/etc/systemd/system/cloudif-npm-backup.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/proxy/etc/systemd/system/cloudif-npm-healthcheck.service`](../components/proxy/etc/systemd/system/cloudif-npm-healthcheck.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/proxy/etc/systemd/system/cloudif-npm-healthcheck.timer`](../components/proxy/etc/systemd/system/cloudif-npm-healthcheck.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/proxy/etc/systemd/system/cloudif-npm-publisher-agent.service`](../components/proxy/etc/systemd/system/cloudif-npm-publisher-agent.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/proxy/etc/systemd/system/cloudif-publication-cert-renew.service`](../components/proxy/etc/systemd/system/cloudif-publication-cert-renew.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/proxy/etc/systemd/system/cloudif-publication-cert-renew.timer`](../components/proxy/etc/systemd/system/cloudif-publication-cert-renew.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/proxy/srv/README.md`](../components/proxy/srv/README.md) | Documentação deste diretório. |
| [`components/proxy/srv/cloudif/README.md`](../components/proxy/srv/cloudif/README.md) | Documentação deste diretório. |
| [`components/proxy/srv/cloudif/proxy/README.md`](../components/proxy/srv/cloudif/proxy/README.md) | Documentação deste diretório. |
| [`components/proxy/srv/cloudif/proxy/npm/README.md`](../components/proxy/srv/cloudif/proxy/npm/README.md) | Documentação deste diretório. |
| [`components/proxy/srv/cloudif/proxy/npm/data/nginx/custom/http.conf`](../components/proxy/srv/cloudif/proxy/npm/data/nginx/custom/http.conf) | Configuração de serviço, proxy ou aplicação. |
| [`components/proxy/srv/cloudif/proxy/npm/data/nginx/custom/server_proxy.conf`](../components/proxy/srv/cloudif/proxy/npm/data/nginx/custom/server_proxy.conf) | Configuração de serviço, proxy ou aplicação. |
| [`components/proxy/usr/README.md`](../components/proxy/usr/README.md) | Documentação deste diretório. |
| [`components/proxy/usr/local/README.md`](../components/proxy/usr/local/README.md) | Documentação deste diretório. |
| [`components/proxy/usr/local/sbin/README.md`](../components/proxy/usr/local/sbin/README.md) | Documentação deste diretório. |
| [`components/proxy/usr/local/sbin/cloudif-configure-komodo-embed.sh`](../components/proxy/usr/local/sbin/cloudif-configure-komodo-embed.sh) | Automação Shell operacional da plataforma. |
| [`components/proxy/usr/local/sbin/cloudif-configure-main-artifact-upload.sh`](../components/proxy/usr/local/sbin/cloudif-configure-main-artifact-upload.sh) | Automação Shell operacional da plataforma. |
| [`components/proxy/usr/local/sbin/cloudif-machine-certificate-renew.py`](../components/proxy/usr/local/sbin/cloudif-machine-certificate-renew.py) | Implementa `load_env`, `run`, `serial`, `cert_expiring`, `opener`, `post` e outros componentes. |
| [`components/proxy/usr/local/sbin/cloudif-machine-executor.py`](../components/proxy/usr/local/sbin/cloudif-machine-executor.py) | Módulo Python da plataforma. |
| [`components/proxy/usr/local/sbin/cloudif-machine-guardian.py`](../components/proxy/usr/local/sbin/cloudif-machine-guardian.py) | Implementa `send`, `main`. |
| [`components/proxy/usr/local/sbin/cloudif-machine-harvester.py`](../components/proxy/usr/local/sbin/cloudif-machine-harvester.py) | Implementa `verify_policy_envelope`, `controller_open`, `run`, `ensure_identity`, `cert_state`, `cert_record` e outros componentes. |
| [`components/proxy/usr/local/sbin/cloudif-node-metrics.py`](../components/proxy/usr/local/sbin/cloudif-node-metrics.py) | Implementa `run`, `network_summary`, `docker_summary`, `metrics`, `H`. |
| [`components/proxy/usr/local/sbin/cloudif-npm-backup.sh`](../components/proxy/usr/local/sbin/cloudif-npm-backup.sh) | Script Shell de backup, retenção ou sincronização. |
| [`components/proxy/usr/local/sbin/cloudif-npm-healthcheck.sh`](../components/proxy/usr/local/sbin/cloudif-npm-healthcheck.sh) | Automação Shell operacional da plataforma. |
| [`components/proxy/usr/local/sbin/cloudif-npm-publisher-agent.py`](../components/proxy/usr/local/sbin/cloudif-npm-publisher-agent.py) | Implementa `env`, `load_state`, `save_state`, `run`, `cert_exists`, `cert_covers` e outros componentes. |
| [`components/proxy/usr/local/sbin/cloudif-publication-cert-renew.sh`](../components/proxy/usr/local/sbin/cloudif-publication-cert-renew.sh) | Automação Shell operacional da plataforma. |
| [`components/proxy/usr/local/sbin/cloudif-release-maintenance`](../components/proxy/usr/local/sbin/cloudif-release-maintenance) | Arquivo de suporte da plataforma. |
| [`components/runtime/README.md`](../components/runtime/README.md) | Documentação deste diretório. |
| [`components/runtime/current-apps/README.md`](../components/runtime/current-apps/README.md) | Documentação deste diretório. |
| [`components/runtime/current-apps/artifact-executor-current/README.md`](../components/runtime/current-apps/artifact-executor-current/README.md) | Documentação deste diretório. |
| [`components/runtime/current-apps/artifact-executor-current/cloudif-artifact-executor.py`](../components/runtime/current-apps/artifact-executor-current/cloudif-artifact-executor.py) | Implementa `db`, `auth`, `sanitize`, `run`, `build`, `H`. |
| [`components/runtime/current-apps/artifact-executor-current/cloudif_multiservice_artifact.py`](../components/runtime/current-apps/artifact-executor-current/cloudif_multiservice_artifact.py) | Implementa `ArtifactError`, `sha256`, `canonical`, `load_env`, `safe_rel`, `normalize_command` e outros componentes. |
| [`components/runtime/current-apps/artifact-executor-current/cloudif_toolchain_policy.py`](../components/runtime/current-apps/artifact-executor-current/cloudif_toolchain_policy.py) | Implementa `canonical`, `digest`, `load_catalog`, `safe_relative_path`, `_item_name_version`, `_resolve_catalog_items` e outros componentes. |
| [`components/runtime/current-apps/forja-agent-current/README.md`](../components/runtime/current-apps/forja-agent-current/README.md) | Documentação deste diretório. |
| [`components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py`](../components/runtime/current-apps/forja-agent-current/cloudif-forja-agent.py) | Implementa `read_env`, `now`, `clean_url`, `bool_value`, `jdump`, `json_response` e outros componentes. |
| [`components/runtime/current-apps/komodo-agent-current/README.md`](../components/runtime/current-apps/komodo-agent-current/README.md) | Documentação deste diretório. |
| [`components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py`](../components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py) | Implementa `now`, `init_db`, `db_exec`, `db_query`, `record_deployment`, `load_env` e outros componentes. |
| [`components/runtime/current-apps/multiservice-deployment-executor-current/README.md`](../components/runtime/current-apps/multiservice-deployment-executor-current/README.md) | Documentação deste diretório. |
| [`components/runtime/current-apps/multiservice-deployment-executor-current/cloudif-multiservice-deployment-executor.py`](../components/runtime/current-apps/multiservice-deployment-executor-current/cloudif-multiservice-deployment-executor.py) | Implementa `DeploymentError`, `canonical`, `db`, `init_db`, `run`, `docker` e outros componentes. |
| [`components/runtime/current-apps/multiservice-preview-executor-current/README.md`](../components/runtime/current-apps/multiservice-preview-executor-current/README.md) | Documentação deste diretório. |
| [`components/runtime/current-apps/multiservice-preview-executor-current/cloudif-multiservice-preview-executor.py`](../components/runtime/current-apps/multiservice-preview-executor-current/cloudif-multiservice-preview-executor.py) | Implementa `PreviewError`, `db`, `init_db`, `docker`, `inspect_image`, `normalize_route` e outros componentes. |
| [`components/runtime/current-apps/node24-pipeline-current/README.md`](../components/runtime/current-apps/node24-pipeline-current/README.md) | Documentação deste diretório. |
| [`components/runtime/current-apps/node24-pipeline-current/cloudif-node24-pipeline.py`](../components/runtime/current-apps/node24-pipeline-current/cloudif-node24-pipeline.py) | Implementa `run`, `sha`, `main`. |
| [`components/runtime/current-apps/preview-executor-current/README.md`](../components/runtime/current-apps/preview-executor-current/README.md) | Documentação deste diretório. |
| [`components/runtime/current-apps/preview-executor-current/cloudif-preview-executor.py`](../components/runtime/current-apps/preview-executor-current/cloudif-preview-executor.py) | Implementa `db`, `auth`, `image_proof`, `create`, `get`, `remove` e outros componentes. |
| [`components/runtime/current-apps/production-canary-executor-current/README.md`](../components/runtime/current-apps/production-canary-executor-current/README.md) | Documentação deste diretório. |
| [`components/runtime/current-apps/production-canary-executor-current/cloudif-production-canary-executor.py`](../components/runtime/current-apps/production-canary-executor-current/cloudif-production-canary-executor.py) | Implementa `db`, `auth`, `cur`, `inspect_image`, `ip`, `smoke` e outros componentes. |
| [`components/runtime/current-apps/production-homologation-executor-current/README.md`](../components/runtime/current-apps/production-homologation-executor-current/README.md) | Documentação deste diretório. |
| [`components/runtime/current-apps/production-homologation-executor-current/cloudif-production-homologation-executor.py`](../components/runtime/current-apps/production-homologation-executor-current/cloudif-production-homologation-executor.py) | Implementa `db`, `auth`, `current`, `image_proof`, `running`, `smoke` e outros componentes. |
| [`components/runtime/current-apps/production-public-executor-current/README.md`](../components/runtime/current-apps/production-public-executor-current/README.md) | Documentação deste diretório. |
| [`components/runtime/current-apps/production-public-executor-current/cloudif-production-public-executor.py`](../components/runtime/current-apps/production-public-executor-current/cloudif-production-public-executor.py) | Implementa `conn`, `auth`, `current`, `run`, `inspect_image`, `netinfo` e outros componentes. |
| [`components/runtime/current-apps/production-sealed-target-current/README.md`](../components/runtime/current-apps/production-sealed-target-current/README.md) | Documentação deste diretório. |
| [`components/runtime/current-apps/production-sealed-target-current/cloudif-production-sealed-target.py`](../components/runtime/current-apps/production-sealed-target-current/cloudif-production-sealed-target.py) | Implementa `state`, `H`. |
| [`components/runtime/etc/README.md`](../components/runtime/etc/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/cloudif-multiservice-deployment-executor.env.example`](../components/runtime/etc/cloudif-multiservice-deployment-executor.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`components/runtime/etc/cloudif-multiservice-preview-executor.env.example`](../components/runtime/etc/cloudif-multiservice-preview-executor.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`components/runtime/etc/cloudif/README.md`](../components/runtime/etc/cloudif/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/cloudif/toolchain-catalog-v1.json`](../components/runtime/etc/cloudif/toolchain-catalog-v1.json) | Configuração, inventário, evidência ou estado serializado em JSON. |
| [`components/runtime/etc/komodo/README.md`](../components/runtime/etc/komodo/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/README.md`](../components/runtime/etc/komodo/stacks/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-atalhos-cloudif-iff1860746/README.md`](../components/runtime/etc/komodo/stacks/cloudif-atalhos-cloudif-iff1860746/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-atalhos-cloudif-iff1860746/docker-compose.yml`](../components/runtime/etc/komodo/stacks/cloudif-atalhos-cloudif-iff1860746/docker-compose.yml) | Definição declarativa de serviços Docker Compose. |
| [`components/runtime/etc/komodo/stacks/cloudif-atalhos-cloudif-iff1860746/nginx.conf`](../components/runtime/etc/komodo/stacks/cloudif-atalhos-cloudif-iff1860746/nginx.conf) | Configuração de serviço, proxy ou aplicação. |
| [`components/runtime/etc/komodo/stacks/cloudif-atalhos-cloudif-iff1860746/site/README.md`](../components/runtime/etc/komodo/stacks/cloudif-atalhos-cloudif-iff1860746/site/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-atalhos-cloudif-iff1860746/site/index.html`](../components/runtime/etc/komodo/stacks/cloudif-atalhos-cloudif-iff1860746/site/index.html) | Interface, protótipo ou evidência HTML. |
| [`components/runtime/etc/komodo/stacks/cloudif-cloudif-v97-test-20260608-201744/README.md`](../components/runtime/etc/komodo/stacks/cloudif-cloudif-v97-test-20260608-201744/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-cloudif-v97-test-20260608-201744/docker-compose.yml`](../components/runtime/etc/komodo/stacks/cloudif-cloudif-v97-test-20260608-201744/docker-compose.yml) | Definição declarativa de serviços Docker Compose. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1006-d2/README.md`](../components/runtime/etc/komodo/stacks/cloudif-p1006-d2/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1006-d2/compose.yaml`](../components/runtime/etc/komodo/stacks/cloudif-p1006-d2/compose.yaml) | Definição declarativa de serviços Docker Compose. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1006-d3/README.md`](../components/runtime/etc/komodo/stacks/cloudif-p1006-d3/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1006-d3/compose.yaml`](../components/runtime/etc/komodo/stacks/cloudif-p1006-d3/compose.yaml) | Definição declarativa de serviços Docker Compose. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1006-d4/README.md`](../components/runtime/etc/komodo/stacks/cloudif-p1006-d4/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1006-d4/compose.yaml`](../components/runtime/etc/komodo/stacks/cloudif-p1006-d4/compose.yaml) | Definição declarativa de serviços Docker Compose. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1006-d5/README.md`](../components/runtime/etc/komodo/stacks/cloudif-p1006-d5/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1006-d5/compose.yaml`](../components/runtime/etc/komodo/stacks/cloudif-p1006-d5/compose.yaml) | Definição declarativa de serviços Docker Compose. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1009-d1/README.md`](../components/runtime/etc/komodo/stacks/cloudif-p1009-d1/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1009-d1/compose.yaml`](../components/runtime/etc/komodo/stacks/cloudif-p1009-d1/compose.yaml) | Definição declarativa de serviços Docker Compose. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1009-d10/README.md`](../components/runtime/etc/komodo/stacks/cloudif-p1009-d10/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1009-d10/compose.yaml`](../components/runtime/etc/komodo/stacks/cloudif-p1009-d10/compose.yaml) | Definição declarativa de serviços Docker Compose. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1009-d11/README.md`](../components/runtime/etc/komodo/stacks/cloudif-p1009-d11/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1009-d11/compose.yaml`](../components/runtime/etc/komodo/stacks/cloudif-p1009-d11/compose.yaml) | Definição declarativa de serviços Docker Compose. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1009-d2/README.md`](../components/runtime/etc/komodo/stacks/cloudif-p1009-d2/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1009-d2/compose.yaml`](../components/runtime/etc/komodo/stacks/cloudif-p1009-d2/compose.yaml) | Definição declarativa de serviços Docker Compose. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1009-d3/README.md`](../components/runtime/etc/komodo/stacks/cloudif-p1009-d3/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1009-d3/compose.yaml`](../components/runtime/etc/komodo/stacks/cloudif-p1009-d3/compose.yaml) | Definição declarativa de serviços Docker Compose. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1009-d4/README.md`](../components/runtime/etc/komodo/stacks/cloudif-p1009-d4/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1009-d4/compose.yaml`](../components/runtime/etc/komodo/stacks/cloudif-p1009-d4/compose.yaml) | Definição declarativa de serviços Docker Compose. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1009-d5/README.md`](../components/runtime/etc/komodo/stacks/cloudif-p1009-d5/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1009-d5/compose.yaml`](../components/runtime/etc/komodo/stacks/cloudif-p1009-d5/compose.yaml) | Definição declarativa de serviços Docker Compose. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1009-d6/README.md`](../components/runtime/etc/komodo/stacks/cloudif-p1009-d6/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1009-d6/compose.yaml`](../components/runtime/etc/komodo/stacks/cloudif-p1009-d6/compose.yaml) | Definição declarativa de serviços Docker Compose. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1009-d7/README.md`](../components/runtime/etc/komodo/stacks/cloudif-p1009-d7/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1009-d7/compose.yaml`](../components/runtime/etc/komodo/stacks/cloudif-p1009-d7/compose.yaml) | Definição declarativa de serviços Docker Compose. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1009-d8/README.md`](../components/runtime/etc/komodo/stacks/cloudif-p1009-d8/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1009-d8/compose.yaml`](../components/runtime/etc/komodo/stacks/cloudif-p1009-d8/compose.yaml) | Definição declarativa de serviços Docker Compose. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1009-d9/README.md`](../components/runtime/etc/komodo/stacks/cloudif-p1009-d9/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-p1009-d9/compose.yaml`](../components/runtime/etc/komodo/stacks/cloudif-p1009-d9/compose.yaml) | Definição declarativa de serviços Docker Compose. |
| [`components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/.cloudif-template.json`](../components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/.cloudif-template.json) | Configuração, inventário, evidência ou estado serializado em JSON. |
| [`components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/README.md`](../components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/docker-compose.yml`](../components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/docker-compose.yml) | Definição declarativa de serviços Docker Compose. |
| [`components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/nginx.conf`](../components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/nginx.conf) | Configuração de serviço, proxy ou aplicação. |
| [`components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/site/README.md`](../components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/site/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/site/app.js`](../components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/site/app.js) | Comportamento JavaScript da interface ou automação. |
| [`components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/site/assets/README.md`](../components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/site/assets/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/site/assets/forgejo.svg`](../components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/site/assets/forgejo.svg) | Arquivo de suporte da plataforma. |
| [`components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/site/assets/komodo.svg`](../components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/site/assets/komodo.svg) | Arquivo de suporte da plataforma. |
| [`components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/site/assets/portal.svg`](../components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/site/assets/portal.svg) | Arquivo de suporte da plataforma. |
| [`components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/site/assets/supabase.svg`](../components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/site/assets/supabase.svg) | Arquivo de suporte da plataforma. |
| [`components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/site/assets/webhooks.svg`](../components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/site/assets/webhooks.svg) | Arquivo de suporte da plataforma. |
| [`components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/site/config.js`](../components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/site/config.js) | Comportamento JavaScript da interface ou automação. |
| [`components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/site/index.html`](../components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/site/index.html) | Interface, protótipo ou evidência HTML. |
| [`components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/site/style.css`](../components/runtime/etc/komodo/stacks/cloudif-primeiros-passos-cloudif-iff1860746/site/style.css) | Estilos da interface web. |
| [`components/runtime/etc/komodo/stacks/cloudif-sistema-de-biblioteca-teste/README.md`](../components/runtime/etc/komodo/stacks/cloudif-sistema-de-biblioteca-teste/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-sistema-de-biblioteca-teste/docker-compose.yml`](../components/runtime/etc/komodo/stacks/cloudif-sistema-de-biblioteca-teste/docker-compose.yml) | Definição declarativa de serviços Docker Compose. |
| [`components/runtime/etc/komodo/stacks/cloudif-sistema-de-biblioteca-teste/nginx.conf`](../components/runtime/etc/komodo/stacks/cloudif-sistema-de-biblioteca-teste/nginx.conf) | Configuração de serviço, proxy ou aplicação. |
| [`components/runtime/etc/komodo/stacks/cloudif-sistema-de-biblioteca-teste/site/README.md`](../components/runtime/etc/komodo/stacks/cloudif-sistema-de-biblioteca-teste/site/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-sistema-de-biblioteca-teste/site/index.html`](../components/runtime/etc/komodo/stacks/cloudif-sistema-de-biblioteca-teste/site/index.html) | Interface, protótipo ou evidência HTML. |
| [`components/runtime/etc/komodo/stacks/cloudif-sistema-de-biblioteca/README.md`](../components/runtime/etc/komodo/stacks/cloudif-sistema-de-biblioteca/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-sistema-de-biblioteca/cloudif-test-v120.txt`](../components/runtime/etc/komodo/stacks/cloudif-sistema-de-biblioteca/cloudif-test-v120.txt) | Artefato de teste ou evidência de validação. |
| [`components/runtime/etc/komodo/stacks/cloudif-sistema-de-biblioteca/cloudif-test-v124.txt`](../components/runtime/etc/komodo/stacks/cloudif-sistema-de-biblioteca/cloudif-test-v124.txt) | Artefato de teste ou evidência de validação. |
| [`components/runtime/etc/komodo/stacks/cloudif-sistema-de-biblioteca/docker-compose.yml`](../components/runtime/etc/komodo/stacks/cloudif-sistema-de-biblioteca/docker-compose.yml) | Definição declarativa de serviços Docker Compose. |
| [`components/runtime/etc/komodo/stacks/cloudif-teste-2/README.md`](../components/runtime/etc/komodo/stacks/cloudif-teste-2/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-teste-2/docker-compose.yml`](../components/runtime/etc/komodo/stacks/cloudif-teste-2/docker-compose.yml) | Definição declarativa de serviços Docker Compose. |
| [`components/runtime/etc/komodo/stacks/cloudif-validacao-botao-cloudif-iff1860746/README.md`](../components/runtime/etc/komodo/stacks/cloudif-validacao-botao-cloudif-iff1860746/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-validacao-botao-cloudif-iff1860746/docker-compose.yml`](../components/runtime/etc/komodo/stacks/cloudif-validacao-botao-cloudif-iff1860746/docker-compose.yml) | Definição declarativa de serviços Docker Compose. |
| [`components/runtime/etc/komodo/stacks/cloudif-validacao-botao-cloudif-iff1860746/nginx.conf`](../components/runtime/etc/komodo/stacks/cloudif-validacao-botao-cloudif-iff1860746/nginx.conf) | Configuração de serviço, proxy ou aplicação. |
| [`components/runtime/etc/komodo/stacks/cloudif-validacao-botao-cloudif-iff1860746/site/README.md`](../components/runtime/etc/komodo/stacks/cloudif-validacao-botao-cloudif-iff1860746/site/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/komodo/stacks/cloudif-validacao-botao-cloudif-iff1860746/site/index.html`](../components/runtime/etc/komodo/stacks/cloudif-validacao-botao-cloudif-iff1860746/site/index.html) | Interface, protótipo ou evidência HTML. |
| [`components/runtime/etc/systemd/README.md`](../components/runtime/etc/systemd/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/systemd/system/README.md`](../components/runtime/etc/systemd/system/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/systemd/system/cloudif-artifact-executor.service`](../components/runtime/etc/systemd/system/cloudif-artifact-executor.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/runtime/etc/systemd/system/cloudif-forja-agent.service`](../components/runtime/etc/systemd/system/cloudif-forja-agent.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/runtime/etc/systemd/system/cloudif-forja-agent.service.d/README.md`](../components/runtime/etc/systemd/system/cloudif-forja-agent.service.d/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/systemd/system/cloudif-forja-agent.service.d/komodo-client.conf`](../components/runtime/etc/systemd/system/cloudif-forja-agent.service.d/komodo-client.conf) | Configuração de serviço, proxy ou aplicação. |
| [`components/runtime/etc/systemd/system/cloudif-komodo-agent.service`](../components/runtime/etc/systemd/system/cloudif-komodo-agent.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/runtime/etc/systemd/system/cloudif-komodo-authz-sync.service`](../components/runtime/etc/systemd/system/cloudif-komodo-authz-sync.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/runtime/etc/systemd/system/cloudif-komodo-authz-sync.timer`](../components/runtime/etc/systemd/system/cloudif-komodo-authz-sync.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/runtime/etc/systemd/system/cloudif-machine-certificate-renew.service`](../components/runtime/etc/systemd/system/cloudif-machine-certificate-renew.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/runtime/etc/systemd/system/cloudif-machine-certificate-renew.timer`](../components/runtime/etc/systemd/system/cloudif-machine-certificate-renew.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/runtime/etc/systemd/system/cloudif-machine-guardian.service`](../components/runtime/etc/systemd/system/cloudif-machine-guardian.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/runtime/etc/systemd/system/cloudif-machine-guardian.timer`](../components/runtime/etc/systemd/system/cloudif-machine-guardian.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/runtime/etc/systemd/system/cloudif-machine-harvester.service`](../components/runtime/etc/systemd/system/cloudif-machine-harvester.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/runtime/etc/systemd/system/cloudif-machine-harvester.timer`](../components/runtime/etc/systemd/system/cloudif-machine-harvester.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/runtime/etc/systemd/system/cloudif-multiservice-deployment-executor.service`](../components/runtime/etc/systemd/system/cloudif-multiservice-deployment-executor.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/runtime/etc/systemd/system/cloudif-multiservice-preview-executor.service`](../components/runtime/etc/systemd/system/cloudif-multiservice-preview-executor.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/runtime/etc/systemd/system/cloudif-node-metrics.service`](../components/runtime/etc/systemd/system/cloudif-node-metrics.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/runtime/etc/systemd/system/cloudif-node24-pipeline.service`](../components/runtime/etc/systemd/system/cloudif-node24-pipeline.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/runtime/etc/systemd/system/cloudif-node24-pipeline.timer`](../components/runtime/etc/systemd/system/cloudif-node24-pipeline.timer) | Timer systemd que agenda a unidade correspondente. |
| [`components/runtime/etc/systemd/system/cloudif-preview-executor.service`](../components/runtime/etc/systemd/system/cloudif-preview-executor.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/runtime/etc/systemd/system/cloudif-production-canary-executor.service`](../components/runtime/etc/systemd/system/cloudif-production-canary-executor.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/runtime/etc/systemd/system/cloudif-production-homologation-executor.service`](../components/runtime/etc/systemd/system/cloudif-production-homologation-executor.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/runtime/etc/systemd/system/cloudif-production-public-executor.service`](../components/runtime/etc/systemd/system/cloudif-production-public-executor.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/runtime/etc/systemd/system/cloudif-production-sealed-target.service`](../components/runtime/etc/systemd/system/cloudif-production-sealed-target.service) | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`components/runtime/etc/systemd/system/cloudif-production-sealed-target.service.d/README.md`](../components/runtime/etc/systemd/system/cloudif-production-sealed-target.service.d/README.md) | Documentação deste diretório. |
| [`components/runtime/etc/systemd/system/cloudif-production-sealed-target.service.d/network.conf`](../components/runtime/etc/systemd/system/cloudif-production-sealed-target.service.d/network.conf) | Configuração de serviço, proxy ou aplicação. |
| [`components/runtime/srv/README.md`](../components/runtime/srv/README.md) | Documentação deste diretório. |
| [`components/runtime/srv/cloudif/README.md`](../components/runtime/srv/cloudif/README.md) | Documentação deste diretório. |
| [`components/runtime/srv/cloudif/publication-gateway/README.md`](../components/runtime/srv/cloudif/publication-gateway/README.md) | Documentação deste diretório. |
| [`components/runtime/srv/cloudif/publication-gateway/conf.d/10-generic-publications.conf`](../components/runtime/srv/cloudif/publication-gateway/conf.d/10-generic-publications.conf) | Configuração de serviço, proxy ou aplicação. |
| [`components/runtime/srv/cloudif/publication-gateway/conf.d/README.md`](../components/runtime/srv/cloudif/publication-gateway/conf.d/README.md) | Documentação deste diretório. |
| [`components/runtime/srv/cloudif/scanners/README.md`](../components/runtime/srv/cloudif/scanners/README.md) | Documentação deste diretório. |
| [`components/runtime/srv/cloudif/scanners/images.env.example`](../components/runtime/srv/cloudif/scanners/images.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`components/runtime/srv/cloudif/scanners/node-distroless-images.env.example`](../components/runtime/srv/cloudif/scanners/node-distroless-images.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`components/runtime/srv/cloudif/scanners/node-images.env.example`](../components/runtime/srv/cloudif/scanners/node-images.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`components/runtime/srv/cloudif/test-fixtures/README.md`](../components/runtime/srv/cloudif/test-fixtures/README.md) | Documentação deste diretório. |
| [`components/runtime/srv/cloudif/test-fixtures/node24-http/README.md`](../components/runtime/srv/cloudif/test-fixtures/node24-http/README.md) | Documentação deste diretório. |
| [`components/runtime/srv/cloudif/test-fixtures/node24-http/package-lock.json`](../components/runtime/srv/cloudif/test-fixtures/node24-http/package-lock.json) | Configuração, inventário, evidência ou estado serializado em JSON. |
| [`components/runtime/srv/cloudif/test-fixtures/node24-http/package.json`](../components/runtime/srv/cloudif/test-fixtures/node24-http/package.json) | Configuração, inventário, evidência ou estado serializado em JSON. |
| [`components/runtime/srv/cloudif/test-fixtures/node24-http/server.js`](../components/runtime/srv/cloudif/test-fixtures/node24-http/server.js) | Comportamento JavaScript da interface ou automação. |
| [`components/runtime/srv/cloudif/test-fixtures/node24-http/server.test.js`](../components/runtime/srv/cloudif/test-fixtures/node24-http/server.test.js) | Comportamento JavaScript da interface ou automação. |
| [`components/runtime/usr/README.md`](../components/runtime/usr/README.md) | Documentação deste diretório. |
| [`components/runtime/usr/local/README.md`](../components/runtime/usr/local/README.md) | Documentação deste diretório. |
| [`components/runtime/usr/local/sbin/README.md`](../components/runtime/usr/local/sbin/README.md) | Documentação deste diretório. |
| [`components/runtime/usr/local/sbin/cloudif-forja-agent.py`](../components/runtime/usr/local/sbin/cloudif-forja-agent.py) | Implementa `read_env`, `now`, `clean_url`, `bool_value`, `jdump`, `json_response` e outros componentes. |
| [`components/runtime/usr/local/sbin/cloudif-komodo-agent.py`](../components/runtime/usr/local/sbin/cloudif-komodo-agent.py) | Implementa `now`, `init_db`, `db_exec`, `db_query`, `record_deployment`, `load_env` e outros componentes. |
| [`components/runtime/usr/local/sbin/cloudif-komodo-api-call.py`](../components/runtime/usr/local/sbin/cloudif-komodo-api-call.py) | Implementa `load_env`, `headers`, `call`. |
| [`components/runtime/usr/local/sbin/cloudif-komodo-authz-sync.py`](../components/runtime/usr/local/sbin/cloudif-komodo-authz-sync.py) | Implementa `run`. |
| [`components/runtime/usr/local/sbin/cloudif-komodo-project-authz.py`](../components/runtime/usr/local/sbin/cloudif-komodo-project-authz.py) | Implementa `main`. |
| [`components/runtime/usr/local/sbin/cloudif-machine-certificate-renew.py`](../components/runtime/usr/local/sbin/cloudif-machine-certificate-renew.py) | Implementa `load_env`, `run`, `serial`, `cert_expiring`, `opener`, `post` e outros componentes. |
| [`components/runtime/usr/local/sbin/cloudif-machine-executor.py`](../components/runtime/usr/local/sbin/cloudif-machine-executor.py) | Módulo Python da plataforma. |
| [`components/runtime/usr/local/sbin/cloudif-machine-guardian.py`](../components/runtime/usr/local/sbin/cloudif-machine-guardian.py) | Implementa `send`, `main`. |
| [`components/runtime/usr/local/sbin/cloudif-machine-harvester.py`](../components/runtime/usr/local/sbin/cloudif-machine-harvester.py) | Implementa `verify_policy_envelope`, `controller_open`, `run`, `ensure_identity`, `cert_state`, `cert_record` e outros componentes. |
| [`components/runtime/usr/local/sbin/cloudif-mongosh-komodo`](../components/runtime/usr/local/sbin/cloudif-mongosh-komodo) | Arquivo de suporte da plataforma. |
| [`components/runtime/usr/local/sbin/cloudif-node-metrics.py`](../components/runtime/usr/local/sbin/cloudif-node-metrics.py) | Implementa `run`, `network_summary`, `docker_summary`, `metrics`, `H`. |
| [`components/runtime/usr/local/sbin/cloudif-release-maintenance`](../components/runtime/usr/local/sbin/cloudif-release-maintenance) | Arquivo de suporte da plataforma. |
| [`config/README.md`](../config/README.md) | Documentação deste diretório. |
| [`config/control-plane/README.md`](../config/control-plane/README.md) | Documentação deste diretório. |
| [`config/control-plane/academic-audit.env.example`](../config/control-plane/academic-audit.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/agent-registry.env.example`](../config/control-plane/agent-registry.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/approvals.env.example`](../config/control-plane/approvals.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/build-broker.env.example`](../config/control-plane/build-broker.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/certificate-monitoring.json`](../config/control-plane/certificate-monitoring.json) | Configuração, inventário, evidência ou estado serializado em JSON. |
| [`config/control-plane/cloudif-authz-gate.env.example`](../config/control-plane/cloudif-authz-gate.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/cloudif-supabase-session.env.example`](../config/control-plane/cloudif-supabase-session.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/cloudif-tenant-guard.env.example`](../config/control-plane/cloudif-tenant-guard.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/control-dashboard.env.example`](../config/control-plane/control-dashboard.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/control-plane.env.example`](../config/control-plane/control-plane.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/deployment-broker.env.example`](../config/control-plane/deployment-broker.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/evaluations.env.example`](../config/control-plane/evaluations.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/machine-admin-security.env.example`](../config/control-plane/machine-admin-security.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/machine-agent.env.example`](../config/control-plane/machine-agent.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/machine-controller-db.env.example`](../config/control-plane/machine-controller-db.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/mcp-gateway.env.example`](../config/control-plane/mcp-gateway.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/monitor.env.example`](../config/control-plane/monitor.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/node-execution-policy.json`](../config/control-plane/node-execution-policy.json) | Política ou configuração declarativa em JSON. |
| [`config/control-plane/node24-homologation.json`](../config/control-plane/node24-homologation.json) | Configuração, inventário, evidência ou estado serializado em JSON. |
| [`config/control-plane/notifications.env.example`](../config/control-plane/notifications.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/policy-signing.pub`](../config/control-plane/policy-signing.pub) | Arquivo de suporte da plataforma. |
| [`config/control-plane/portal-qa.env.example`](../config/control-plane/portal-qa.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/portal.env.example`](../config/control-plane/portal.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/preview-broker.env.example`](../config/control-plane/preview-broker.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/preview-cleanup.env.example`](../config/control-plane/preview-cleanup.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/production-targets.json`](../config/control-plane/production-targets.json) | Configuração, inventário, evidência ou estado serializado em JSON. |
| [`config/control-plane/project-capabilities-policy.json`](../config/control-plane/project-capabilities-policy.json) | Política ou configuração declarativa em JSON. |
| [`config/control-plane/project-onboarding.env.example`](../config/control-plane/project-onboarding.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/runtime-policy.json`](../config/control-plane/runtime-policy.json) | Política ou configuração declarativa em JSON. |
| [`config/control-plane/storage-guard.env.example`](../config/control-plane/storage-guard.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/supabase-launch.env.example`](../config/control-plane/supabase-launch.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/supabase-onboarding-broker.env.example`](../config/control-plane/supabase-onboarding-broker.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/supabase-release-agent.env.example`](../config/control-plane/supabase-release-agent.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/transaction-reconciler.env.example`](../config/control-plane/transaction-reconciler.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/control-plane/workspace-broker.env.example`](../config/control-plane/workspace-broker.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/portal-quality-baseline.json`](../config/portal-quality-baseline.json) | Configuração, inventário, evidência ou estado serializado em JSON. |
| [`config/proxy/README.md`](../config/proxy/README.md) | Documentação deste diretório. |
| [`config/proxy/access-push.env.example`](../config/proxy/access-push.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/proxy/access-telemetry.env.example`](../config/proxy/access-telemetry.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/proxy/certificate-monitoring.json`](../config/proxy/certificate-monitoring.json) | Configuração, inventário, evidência ou estado serializado em JSON. |
| [`config/proxy/machine-agent.env.example`](../config/proxy/machine-agent.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/proxy/policy-signing.pub`](../config/proxy/policy-signing.pub) | Arquivo de suporte da plataforma. |
| [`config/runtime/README.md`](../config/runtime/README.md) | Documentação deste diretório. |
| [`config/runtime/artifact-executor.env.example`](../config/runtime/artifact-executor.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/runtime/certificate-monitoring.json`](../config/runtime/certificate-monitoring.json) | Configuração, inventário, evidência ou estado serializado em JSON. |
| [`config/runtime/forja-agent.env.example`](../config/runtime/forja-agent.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/runtime/machine-agent.env.example`](../config/runtime/machine-agent.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/runtime/policy-signing.pub`](../config/runtime/policy-signing.pub) | Arquivo de suporte da plataforma. |
| [`config/runtime/preview-executor.env.example`](../config/runtime/preview-executor.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/runtime/production-canary.env.example`](../config/runtime/production-canary.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/runtime/production-homologation-executor.env.example`](../config/runtime/production-homologation-executor.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`config/runtime/production-public.env.example`](../config/runtime/production-public.env.example) | Modelo de variáveis de ambiente; não deve conter segredos reais. |
| [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) | Documento técnico ou operacional. |
| [`docs/CATALOGO-DE-AGENTES.md`](../docs/CATALOGO-DE-AGENTES.md) | Documento técnico ou operacional. |
| [`docs/CATALOGO-DE-ROTAS.md`](../docs/CATALOGO-DE-ROTAS.md) | Documento técnico ou operacional. |
| [`docs/CATALOGO-DE-SERVICOS.md`](../docs/CATALOGO-DE-SERVICOS.md) | Documento técnico ou operacional. |
| [`docs/COVERAGE_AUDIT.json`](../docs/COVERAGE_AUDIT.json) | Configuração, inventário, evidência ou estado serializado em JSON. |
| [`docs/DICIONARIO-DE-DADOS-ESTATICO.md`](../docs/DICIONARIO-DE-DADOS-ESTATICO.md) | Documento técnico ou operacional. |
| [`docs/DOCUMENTATION-MANIFEST.json`](../docs/DOCUMENTATION-MANIFEST.json) | Configuração, inventário, evidência ou estado serializado em JSON. |
| [`docs/FLUXO-WHP-PUBLICACAO.md`](../docs/FLUXO-WHP-PUBLICACAO.md) | Documento técnico ou operacional. |
| [`docs/GUIA-DE-MIGRACAO.md`](../docs/GUIA-DE-MIGRACAO.md) | Documento técnico ou operacional. |
| [`docs/INVENTARIO-DE-ARQUIVOS.md`](../docs/INVENTARIO-DE-ARQUIVOS.md) | Documento técnico ou operacional. |
| [`docs/INVENTORY.json`](../docs/INVENTORY.json) | Configuração, inventário, evidência ou estado serializado em JSON. |
| [`docs/MAINTENANCE.md`](../docs/MAINTENANCE.md) | Documento técnico ou operacional. |
| [`docs/PLANO-DE-APERFEICOAMENTO.md`](../docs/PLANO-DE-APERFEICOAMENTO.md) | Documento técnico ou operacional. |
| [`docs/README.md`](../docs/README.md) | Documentação deste diretório. |
| [`docs/REPOSITORY_AUDIT.md`](../docs/REPOSITORY_AUDIT.md) | Documento técnico ou operacional. |
| [`docs/REQUIREMENTS.md`](../docs/REQUIREMENTS.md) | Documento técnico ou operacional. |
| [`docs/assets/README.md`](../docs/assets/README.md) | Documentação deste diretório. |
| [`docs/assets/cloudiff-algoritmos-operacionais.svg`](../docs/assets/cloudiff-algoritmos-operacionais.svg) | Arquivo de suporte da plataforma. |
| [`docs/assets/cloudiff-fluxo-whp.svg`](../docs/assets/cloudiff-fluxo-whp.svg) | Arquivo de suporte da plataforma. |
| [`docs/assets/cloudiff-interface.jpg`](../docs/assets/cloudiff-interface.jpg) | Arquivo de suporte da plataforma. |
| [`docs/manual-tecnico/01-ARQUITETURA.md`](../docs/manual-tecnico/01-ARQUITETURA.md) | Documento técnico ou operacional. |
| [`docs/manual-tecnico/02-FLUXOS.md`](../docs/manual-tecnico/02-FLUXOS.md) | Documento técnico ou operacional. |
| [`docs/manual-tecnico/03-AGENTES.md`](../docs/manual-tecnico/03-AGENTES.md) | Documento técnico ou operacional. |
| [`docs/manual-tecnico/04-RECONCILIACAO.md`](../docs/manual-tecnico/04-RECONCILIACAO.md) | Documento técnico ou operacional. |
| [`docs/manual-tecnico/05-DADOS.md`](../docs/manual-tecnico/05-DADOS.md) | Documento técnico ou operacional. |
| [`docs/manual-tecnico/06-MENSAGENS-E-APROVACOES.md`](../docs/manual-tecnico/06-MENSAGENS-E-APROVACOES.md) | Documento técnico ou operacional. |
| [`docs/manual-tecnico/07-OPERACAO.md`](../docs/manual-tecnico/07-OPERACAO.md) | Documento técnico ou operacional. |
| [`docs/manual-tecnico/08-MODELO-DE-SOFTWARE.md`](../docs/manual-tecnico/08-MODELO-DE-SOFTWARE.md) | Documento técnico ou operacional. |
| [`docs/manual-tecnico/09-SERVICOS.md`](../docs/manual-tecnico/09-SERVICOS.md) | Documento técnico ou operacional. |
| [`docs/manual-tecnico/10-DESENVOLVIMENTO.md`](../docs/manual-tecnico/10-DESENVOLVIMENTO.md) | Documento técnico ou operacional. |
| [`docs/manual-tecnico/11-RUNTIME-UNIFICADO.md`](../docs/manual-tecnico/11-RUNTIME-UNIFICADO.md) | Documento técnico ou operacional. |
| [`docs/manual-tecnico/12-ARQUITETURA-OPERACIONAL-ATUAL.md`](../docs/manual-tecnico/12-ARQUITETURA-OPERACIONAL-ATUAL.md) | Documento técnico ou operacional. |
| [`docs/manual-tecnico/13-ACESSO-EXTERNO.md`](../docs/manual-tecnico/13-ACESSO-EXTERNO.md) | Documento técnico ou operacional. |
| [`docs/manual-tecnico/README.md`](../docs/manual-tecnico/README.md) | Documentação deste diretório. |
| [`docs/portal-v2/EXECUTION-CHECKLIST.md`](../docs/portal-v2/EXECUTION-CHECKLIST.md) | Documento técnico ou operacional. |
| [`docs/portal-v2/GUIA-DE-MIGRACAO.md`](../docs/portal-v2/GUIA-DE-MIGRACAO.md) | Documento técnico ou operacional. |
| [`docs/portal-v2/PLANO-DE-APERFEICOAMENTO.md`](../docs/portal-v2/PLANO-DE-APERFEICOAMENTO.md) | Documento técnico ou operacional. |
| [`docs/portal-v2/README.md`](../docs/portal-v2/README.md) | Documentação deste diretório. |
| [`docs/portal-v2/REAL-PAGE-PROOF.json`](../docs/portal-v2/REAL-PAGE-PROOF.json) | Configuração, inventário, evidência ou estado serializado em JSON. |
| [`docs/portal-v2/portal-v2-prototipo.html`](../docs/portal-v2/portal-v2-prototipo.html) | Interface, protótipo ou evidência HTML. |
| [`docs/portal-v2/prototipo.html`](../docs/portal-v2/prototipo.html) | Interface, protótipo ou evidência HTML. |
| [`portal/FROZEN_SURFACES.md`](../portal/FROZEN_SURFACES.md) | Documento técnico ou operacional. |
| [`portal/README.md`](../portal/README.md) | Documentação deste diretório. |
| [`portal/__init__.py`](../portal/__init__.py) | CloudIFF Portal v2 foundation; legacy remains the production fallback. |
| [`portal/app.py`](../portal/app.py) | Coexistence entry point for Portal v2 |
| [`portal/config/README.md`](../portal/config/README.md) | Documentação deste diretório. |
| [`portal/config/permissions-v1-observed.json`](../portal/config/permissions-v1-observed.json) | Política ou configuração declarativa em JSON. |
| [`portal/core/README.md`](../portal/core/README.md) | Documentação deste diretório. |
| [`portal/core/__init__.py`](../portal/core/__init__.py) | Shared Portal v2 core services. |
| [`portal/core/auth.py`](../portal/core/auth.py) | Authentication identity contract; Authentik remains the source of truth. |
| [`portal/core/dispatch.py`](../portal/core/dispatch.py) | Edge dispatcher: resolve route, enforce permission once, then call the view |
| [`portal/core/errors.py`](../portal/core/errors.py) | User-facing empty and error states. |
| [`portal/core/http.py`](../portal/core/http.py) | HTTP request/response contracts shared by migrated Portal v2 modules |
| [`portal/core/legacy_bridge.py`](../portal/core/legacy_bridge.py) | Bridge to the v1 panel modules that carry real business logic |
| [`portal/core/legacy_shell.py`](../portal/core/legacy_shell.py) | Adapt legacy GET pages into the canonical Portal v2 shell |
| [`portal/core/rbac.py`](../portal/core/rbac.py) | Permission decisions for Portal v2 |
| [`portal/core/security.py`](../portal/core/security.py) | Edge security primitives: CSRF and same-origin, reproduced from the v1 |
| [`portal/design/README.md`](../portal/design/README.md) | Documentação deste diretório. |
| [`portal/design/app.js`](../portal/design/app.js) | Comportamento JavaScript da interface ou automação. |
| [`portal/design/base.css`](../portal/design/base.css) | Estilos da interface web. |
| [`portal/design/components.css`](../portal/design/components.css) | Estilos da interface web. |
| [`portal/design/tokens.css`](../portal/design/tokens.css) | Estilos da interface web. |
| [`portal/legacy/README.md`](../portal/legacy/README.md) | Documentação deste diretório. |
| [`portal/legacy/cloudif-admin-portal-base.py`](../portal/legacy/cloudif-admin-portal-base.py) | Implementa `now_iso`, `h`, `norm`, `slugify`, `parse_groups`, `_ensure_db_anchor` e outros componentes. |
| [`portal/legacy/cloudif-admin-portal.py`](../portal/legacy/cloudif-admin-portal.py) | CloudIFF portal launcher with canonical authorization and UI normalization. |
| [`portal/legacy/cloudif_ai_agents_guide.py`](../portal/legacy/cloudif_ai_agents_guide.py) | Implementa `e`, `tools`, `links`, `guide_data`, `oauth_fields`, `actions_schema_url` e outros componentes. |
| [`portal/legacy/cloudif_approval_panel.py`](../portal/legacy/cloudif_approval_panel.py) | Implementa `request`, `sanitize`, `filter_rows`, `sanitize_policy`, `filter_policies`, `fmt_epoch` e outros componentes. |
| [`portal/legacy/cloudif_portal_publications.py`](../portal/legacy/cloudif_portal_publications.py) | Implementa `_env`, `_post`, `_project_allowed`, `_ensure_schema`, `_number`, `_clients` e outros componentes. |
| [`portal/legacy/cloudif_portal_sections98.py`](../portal/legacy/cloudif_portal_sections98.py) | Implementa `e`, `jload`, `dbcount`, `active`, `shell`, `cards` e outros componentes. |
| [`portal/legacy/cloudif_production_operations_panel.py`](../portal/legacy/cloudif_production_operations_panel.py) | Implementa `read_json`, `data`, `esc`, `badge`, `render`. |
| [`portal/legacy/cloudif_project_capabilities_panel.py`](../portal/legacy/cloudif_project_capabilities_panel.py) | Implementa `e`, `data`, `render`. |
| [`portal/legacy/cloudif_project_identity_panel.py`](../portal/legacy/cloudif_project_identity_panel.py) | Implementa `fetch`, `visible`, `badge`, `role_badge`, `permission_summary`, `approval_list` e outros componentes. |
| [`portal/legacy/cloudif_promotion_panel.py`](../portal/legacy/cloudif_promotion_panel.py) | Implementa `fetch`, `e`, `render`. |
| [`portal/legacy/cloudif_publication_panel.py`](../portal/legacy/cloudif_publication_panel.py) | Implementa `node24_status`, `data`, `render`. |
| [`portal/legacy/cloudif_reconcile_panel.py`](../portal/legacy/cloudif_reconcile_panel.py) | Implementa `e`, `data`, `render`. |
| [`portal/legacy/cloudif_transaction_panel.py`](../portal/legacy/cloudif_transaction_panel.py) | Implementa `fetch`, `fmt`, `esc`, `badge`, `render`. |
| [`portal/legacy/cloudif_ui_publications.py`](../portal/legacy/cloudif_ui_publications.py) | Implementa `h`, `_rows`, `_runtime_from_job`, `_komodo_web_status`, `_project_context`, `_project_information` e outros componentes. |
| [`portal/legacy/cloudif_unique_pages98.py`](../portal/legacy/cloudif_unique_pages98.py) | Implementa `e`, `load`, `hero`, `shell`, `agent_management`, `mcp_docs` e outros componentes. |
| [`portal/modules/README.md`](../portal/modules/README.md) | Documentação deste diretório. |
| [`portal/modules/__init__.py`](../portal/modules/__init__.py) | Pluggable modules |
| [`portal/modules/admin/README.md`](../portal/modules/admin/README.md) | Documentação deste diretório. |
| [`portal/modules/admin/__init__.py`](../portal/modules/admin/__init__.py) | admin module: Administração: rotação de credenciais e guia de agentes |
| [`portal/modules/admin/routes.py`](../portal/modules/admin/routes.py) | admin module — route table |
| [`portal/modules/admin/service.py`](../portal/modules/admin/service.py) | admin — dados administrativos |
| [`portal/modules/admin/views.py`](../portal/modules/admin/views.py) | admin — HTML via portal.ui |
| [`portal/modules/delivery/README.md`](../portal/modules/delivery/README.md) | Documentação deste diretório. |
| [`portal/modules/delivery/__init__.py`](../portal/modules/delivery/__init__.py) | delivery module: Entrega: terminal de projeto e histórico de promoções |
| [`portal/modules/delivery/routes.py`](../portal/modules/delivery/routes.py) | delivery module — route table |
| [`portal/modules/delivery/service.py`](../portal/modules/delivery/service.py) | delivery — dados de entrega |
| [`portal/modules/delivery/views.py`](../portal/modules/delivery/views.py) | delivery — HTML via portal.ui |
| [`portal/modules/environments/README.md`](../portal/modules/environments/README.md) | Documentação deste diretório. |
| [`portal/modules/environments/__init__.py`](../portal/modules/environments/__init__.py) | environments module: Operações de produção: janela de mudança, alertas e ciclo de incidentes |
| [`portal/modules/environments/routes.py`](../portal/modules/environments/routes.py) | environments module — route table |
| [`portal/modules/environments/service.py`](../portal/modules/environments/service.py) | environments — dados de produção |
| [`portal/modules/environments/views.py`](../portal/modules/environments/views.py) | environments — HTML via portal.ui |
| [`portal/modules/health/README.md`](../portal/modules/health/README.md) | Documentação deste diretório. |
| [`portal/modules/health/__init__.py`](../portal/modules/health/__init__.py) | health module: system health, repair dashboard and read-only monitors |
| [`portal/modules/health/routes.py`](../portal/modules/health/routes.py) | health module — route table |
| [`portal/modules/health/service.py`](../portal/modules/health/service.py) | health module — business/data layer |
| [`portal/modules/health/views.py`](../portal/modules/health/views.py) | health module — HTML assembly via portal.ui only |
| [`portal/modules/overview/README.md`](../portal/modules/overview/README.md) | Documentação deste diretório. |
| [`portal/modules/overview/__init__.py`](../portal/modules/overview/__init__.py) | overview module: Inicio: painel consolidado (cards, servidores CloudIF) |
| [`portal/modules/overview/routes.py`](../portal/modules/overview/routes.py) | overview module — route table |
| [`portal/modules/overview/service.py`](../portal/modules/overview/service.py) | Read-only data for the academic overview. |
| [`portal/modules/overview/views.py`](../portal/modules/overview/views.py) | Minimal, instructional academic overview. |
| [`portal/modules/projects/README.md`](../portal/modules/projects/README.md) | Documentação deste diretório. |
| [`portal/modules/projects/__init__.py`](../portal/modules/projects/__init__.py) | projects module: Projetos: ações de projeto, publicação e APIs de leitura de projeto |
| [`portal/modules/projects/routes.py`](../portal/modules/projects/routes.py) | projects module — route table |
| [`portal/modules/projects/service.py`](../portal/modules/projects/service.py) | projects.service — visibilidade de projetos por usuário (fiel à v1) |
| [`portal/modules/projects/views.py`](../portal/modules/projects/views.py) | projects.views — HTML da página de Projetos (fiel à v1, com formulários reais) |
| [`portal/registry.py`](../portal/registry.py) | Route registry for the incremental Portal v2 migration |
| [`portal/tests/README.md`](../portal/tests/README.md) | Documentação deste diretório. |
| [`portal/tests/__init__.py`](../portal/tests/__init__.py) | Módulo Python da plataforma. |
| [`portal/tests/test_active_toolchain_consumption.py`](../portal/tests/test_active_toolchain_consumption.py) | Implementa `load`, `ActiveToolchainConsumptionTests`, `sqlite_connection`. |
| [`portal/tests/test_admin_delete_agent_integration_contract.py`](../portal/tests/test_admin_delete_agent_integration_contract.py) | Implementa `AdminDeleteAgentIntegrationContractTest`. |
| [`portal/tests/test_admin_delete_complete_resource_contract.py`](../portal/tests/test_admin_delete_complete_resource_contract.py) | Implementa `AdminDeleteCompleteResourceContractTest`. |
| [`portal/tests/test_admin_delete_identity_observability_contract.py`](../portal/tests/test_admin_delete_identity_observability_contract.py) | Implementa `AdminDeleteIdentityObservabilityContractTest`. |
| [`portal/tests/test_admin_project_delete_contract.py`](../portal/tests/test_admin_project_delete_contract.py) | Implementa `AdminProjectDeleteContractTest`. |
| [`portal/tests/test_admin_project_delete_runtime_contract.py`](../portal/tests/test_admin_project_delete_runtime_contract.py) | Implementa `AdminProjectDeleteRuntimeContractTest`. |
| [`portal/tests/test_ai_connectors_hub.py`](../portal/tests/test_ai_connectors_hub.py) | Implementa `AIConnectorsHubTests`. |
| [`portal/tests/test_approval_cancel.py`](../portal/tests/test_approval_cancel.py) | Implementa `load_api`, `ApprovalCancelTests`. |
| [`portal/tests/test_artifact_upload_agent_handoff.py`](../portal/tests/test_artifact_upload_agent_handoff.py) | Implementa `ArtifactUploadAgentHandoffTests`. |
| [`portal/tests/test_authz_gate_tenant_allowlist.py`](../portal/tests/test_authz_gate_tenant_allowlist.py) | Implementa `load_module`, `AuthzGateTenantAllowlistTests`. |
| [`portal/tests/test_backup_console_json_and_sections.py`](../portal/tests/test_backup_console_json_and_sections.py) | Implementa `BackupConsoleJsonAndSectionsTests`. |
| [`portal/tests/test_backup_progress_modal.py`](../portal/tests/test_backup_progress_modal.py) | Implementa `BackupProgressModalTests`. |
| [`portal/tests/test_backup_remote_global_config.py`](../portal/tests/test_backup_remote_global_config.py) | Implementa `BackupRemoteGlobalConfigTests`. |
| [`portal/tests/test_backup_role_visibility_policy.py`](../portal/tests/test_backup_role_visibility_policy.py) | Implementa `BackupRoleVisibilityPolicyTests`. |
| [`portal/tests/test_build_bound_preview_deployment_contract.py`](../portal/tests/test_build_bound_preview_deployment_contract.py) | Implementa `load_gateway`, `runtime_executor_path`, `BuildBoundPreviewDeploymentContractTests`. |
| [`portal/tests/test_canonical_help_videos.py`](../portal/tests/test_canonical_help_videos.py) | Implementa `CanonicalHelpVideosTests`. |
| [`portal/tests/test_change_set_argument_contract.py`](../portal/tests/test_change_set_argument_contract.py) | Implementa `load_module`, `ChangeSetArgumentContractTests`. |
| [`portal/tests/test_change_set_mcp_contract.py`](../portal/tests/test_change_set_mcp_contract.py) | Implementa `ChangeSetMCPContractTests`. |
| [`portal/tests/test_concurrent_project_tenant_operations.py`](../portal/tests/test_concurrent_project_tenant_operations.py) | Implementa `ConcurrentProjectTenantOperationsTests`. |
| [`portal/tests/test_connector_public_oauth_onboarding.py`](../portal/tests/test_connector_public_oauth_onboarding.py) | Implementa `ConnectorPublicOAuthOnboardingTest`. |
| [`portal/tests/test_dark_theme_legacy_surfaces.py`](../portal/tests/test_dark_theme_legacy_surfaces.py) | Implementa `DarkThemeLegacySurfacesTest`. |
| [`portal/tests/test_database_active_mode_fallback.py`](../portal/tests/test_database_active_mode_fallback.py) | Implementa `DatabaseActiveModeFallbackTests`. |
| [`portal/tests/test_deployment_sensitive_runtime_security.py`](../portal/tests/test_deployment_sensitive_runtime_security.py) | Implementa `load`, `DeploymentSecretInjectionSecurityTests`. |
| [`portal/tests/test_effective_environment_build_contract.py`](../portal/tests/test_effective_environment_build_contract.py) | Implementa `load_artifact`, `EffectiveEnvironmentBuildContractTests`. |
| [`portal/tests/test_forgejo_merge_sha_resolution.py`](../portal/tests/test_forgejo_merge_sha_resolution.py) | Implementa `FakeForgejo`, `forja_namespace`, `ForgejoMergeShaResolutionTests`. |
| [`portal/tests/test_forgejo_webhook_automation_contract.py`](../portal/tests/test_forgejo_webhook_automation_contract.py) | Implementa `ForgejoWebhookAutomationContractTest`. |
| [`portal/tests/test_forja_agent_only_provisioning.py`](../portal/tests/test_forja_agent_only_provisioning.py) | Implementa `ForjaAgentOnlyProvisioningTests`. |
| [`portal/tests/test_forja_change_set_proposal.py`](../portal/tests/test_forja_change_set_proposal.py) | Implementa `FakeForgejo`, `namespace`, `payload`, `ForjaChangeSetProposalTests`. |
| [`portal/tests/test_forja_komodo_client_unit_contract.py`](../portal/tests/test_forja_komodo_client_unit_contract.py) | Implementa `ForjaKomodoClientUnitContractTest`. |
| [`portal/tests/test_forja_personal_owner_and_komodo_payload.py`](../portal/tests/test_forja_personal_owner_and_komodo_payload.py) | Implementa `ForjaPersonalOwnerAndKomodoPayloadTests`. |
| [`portal/tests/test_frozen_surfaces_contract.py`](../portal/tests/test_frozen_surfaces_contract.py) | Implementa `FrozenSurfacesContractTests`. |
| [`portal/tests/test_grouped_resources.py`](../portal/tests/test_grouped_resources.py) | Implementa `GroupedResourcesTest`, `IndividualPublicationTest`, `IndividualPublicationPresentationTest`. |
| [`portal/tests/test_help_external_connections.py`](../portal/tests/test_help_external_connections.py) | Implementa `HelpExternalConnectionsTests`. |
| [`portal/tests/test_help_youtube_videos.py`](../portal/tests/test_help_youtube_videos.py) | Implementa `HelpYoutubeVideosTests`. |
| [`portal/tests/test_initial_publication_immutable_recovery.py`](../portal/tests/test_initial_publication_immutable_recovery.py) | Implementa `load_module`, `InitialPublicationImmutableRecoveryTests`. |
| [`portal/tests/test_initial_publication_local_health_fastpath.py`](../portal/tests/test_initial_publication_local_health_fastpath.py) | Implementa `InitialPublicationVersionedRuntimeTests`. |
| [`portal/tests/test_initial_publication_readiness_contract.py`](../portal/tests/test_initial_publication_readiness_contract.py) | Implementa `InitialPublicationReadinessContractTest`. |
| [`portal/tests/test_komodo_destroy_completion_contract.py`](../portal/tests/test_komodo_destroy_completion_contract.py) | Implementa `KomodoDestroyCompletionContractTest`. |
| [`portal/tests/test_komodo_force_rebuild.py`](../portal/tests/test_komodo_force_rebuild.py) | Implementa `KomodoForceRebuildTests`. |
| [`portal/tests/test_komodo_local_health_json.py`](../portal/tests/test_komodo_local_health_json.py) | Implementa `KomodoLocalHealthJsonTests`. |
| [`portal/tests/test_komodo_local_health_reconciliation.py`](../portal/tests/test_komodo_local_health_reconciliation.py) | Implementa `KomodoLocalHealthReconciliationTests`. |
| [`portal/tests/test_komodo_unified_layout_ensure.py`](../portal/tests/test_komodo_unified_layout_ensure.py) | Implementa `KomodoUnifiedLayoutEnsureTests`. |
| [`portal/tests/test_legacy_shell.py`](../portal/tests/test_legacy_shell.py) | Implementa `LegacyShellTest`. |
| [`portal/tests/test_mcp_actionable_error_contract.py`](../portal/tests/test_mcp_actionable_error_contract.py) | Implementa `load_gateway`, `MCPActionableErrorContractTests`. |
| [`portal/tests/test_mcp_documentation_catalog_parity.py`](../portal/tests/test_mcp_documentation_catalog_parity.py) | Implementa `load`, `MCPDocumentationCatalogParityTests`. |
| [`portal/tests/test_mcp_oauth_contract.py`](../portal/tests/test_mcp_oauth_contract.py) | Implementa `MCPOAuthContractTests`. |
| [`portal/tests/test_mcp_public_oauth_flow.py`](../portal/tests/test_mcp_public_oauth_flow.py) | Implementa `free_port`, `FakeControl`, `FakeAgent`, `MCPPublicOAuthFlowTest`. |
| [`portal/tests/test_membership_reconciliation.py`](../portal/tests/test_membership_reconciliation.py) | Implementa `MembershipReconciliationTests`. |
| [`portal/tests/test_multiservice_artifact_policy.py`](../portal/tests/test_multiservice_artifact_policy.py) | Implementa `MultiserviceArtifactPolicyTests`. |
| [`portal/tests/test_multiservice_build_broker.py`](../portal/tests/test_multiservice_build_broker.py) | Implementa `MultiserviceBuildBrokerTests`. |
| [`portal/tests/test_multiservice_build_mcp_contract.py`](../portal/tests/test_multiservice_build_mcp_contract.py) | Implementa `MultiserviceBuildMCPContractTests`. |
| [`portal/tests/test_multiservice_deployment_execution.py`](../portal/tests/test_multiservice_deployment_execution.py) | Implementa `load_module`, `MultiserviceDeploymentExecutionTests`. |
| [`portal/tests/test_multiservice_deployment_execution_mcp_contract.py`](../portal/tests/test_multiservice_deployment_execution_mcp_contract.py) | Implementa `MultiserviceDeploymentExecutionMCPContractTests`. |
| [`portal/tests/test_multiservice_deployment_executor.py`](../portal/tests/test_multiservice_deployment_executor.py) | Implementa `load_module`, `MultiserviceDeploymentExecutorTests`. |
| [`portal/tests/test_multiservice_deployment_mcp_contract.py`](../portal/tests/test_multiservice_deployment_mcp_contract.py) | Implementa `MultiserviceDeploymentMCPContractTests`. |
| [`portal/tests/test_multiservice_deployment_plan.py`](../portal/tests/test_multiservice_deployment_plan.py) | Implementa `load_module`, `MultiserviceDeploymentPlanTests`. |
| [`portal/tests/test_multiservice_preview_broker.py`](../portal/tests/test_multiservice_preview_broker.py) | Implementa `PreviewBrokerTests`. |
| [`portal/tests/test_multiservice_preview_executor.py`](../portal/tests/test_multiservice_preview_executor.py) | Implementa `PreviewExecutorTests`. |
| [`portal/tests/test_multiservice_preview_mcp_contract.py`](../portal/tests/test_multiservice_preview_mcp_contract.py) | Implementa `PreviewMCPContractTests`. |
| [`portal/tests/test_multiservice_runtime_config_contract.py`](../portal/tests/test_multiservice_runtime_config_contract.py) | Implementa `load_broker`, `MultiserviceRuntimeConfigContractTests`. |
| [`portal/tests/test_multitech_mcp_contract.py`](../portal/tests/test_multitech_mcp_contract.py) | Implementa `MultitechMCPContractTests`. |
| [`portal/tests/test_multitech_recursive_detector.py`](../portal/tests/test_multitech_recursive_detector.py) | Implementa `load_module`, `MultitechRecursiveDetectorTests`. |
| [`portal/tests/test_navigation_information_architecture.py`](../portal/tests/test_navigation_information_architecture.py) | Implementa `NavigationInformationArchitectureTest`. |
| [`portal/tests/test_node_php_mixed_runtime.py`](../portal/tests/test_node_php_mixed_runtime.py) | Implementa `NodePhpMixedRuntimeTests`. |
| [`portal/tests/test_overview_sites.py`](../portal/tests/test_overview_sites.py) | Implementa `OverviewSiteCardTest`. |
| [`portal/tests/test_permission_table.py`](../portal/tests/test_permission_table.py) | A2 acceptance: every migrated v2 guard decides exactly as the v1 table |
| [`portal/tests/test_persistent_approval_portal_contract.py`](../portal/tests/test_persistent_approval_portal_contract.py) | Implementa `PersistentApprovalPortalContractTests`. |
| [`portal/tests/test_persistent_human_approval_policy.py`](../portal/tests/test_persistent_human_approval_policy.py) | Implementa `load_api`, `PersistentHumanApprovalPolicyTests`. |
| [`portal/tests/test_personal_repo_survives_initial_publish.py`](../portal/tests/test_personal_repo_survives_initial_publish.py) | Implementa `PersonalRepoSurvivesInitialPublishTests`. |
| [`portal/tests/test_platform_backup_progress_modal.py`](../portal/tests/test_platform_backup_progress_modal.py) | Implementa `PlatformBackupProgressModalTests`. |
| [`portal/tests/test_platform_guide_canonical.py`](../portal/tests/test_platform_guide_canonical.py) | Implementa `CanonicalPlatformGuideTests`. |
| [`portal/tests/test_platform_guide_github.py`](../portal/tests/test_platform_guide_github.py) | Implementa `PlatformGuideGithubTests`. |
| [`portal/tests/test_portal_approval_redirect_v2.py`](../portal/tests/test_portal_approval_redirect_v2.py) | Implementa `PortalApprovalRedirectV2Tests`. |
| [`portal/tests/test_portal_artifact_upload_bridge.py`](../portal/tests/test_portal_artifact_upload_bridge.py) | Implementa `Response`, `Handler`, `PortalArtifactUploadBridgeTests`. |
| [`portal/tests/test_portal_artifact_upload_routes.py`](../portal/tests/test_portal_artifact_upload_routes.py) | Implementa `PortalArtifactUploadRoutesTests`. |
| [`portal/tests/test_portal_launcher_base_compatibility.py`](../portal/tests/test_portal_launcher_base_compatibility.py) | Implementa `PortalLauncherBaseCompatibilityTests`. |
| [`portal/tests/test_portal_no_legacy_visual_fallback.py`](../portal/tests/test_portal_no_legacy_visual_fallback.py) | Implementa `PortalNoLegacyVisualFallbackTests`. |
| [`portal/tests/test_portal_sqlite_wal_resilience.py`](../portal/tests/test_portal_sqlite_wal_resilience.py) | Implementa `load_delete_module`, `PortalSQLiteWalResilienceTests`. |
| [`portal/tests/test_project_acl_visual_layout.py`](../portal/tests/test_project_acl_visual_layout.py) | Implementa `ProjectAclVisualLayoutTests`. |
| [`portal/tests/test_project_backup_download_public_route.py`](../portal/tests/test_project_backup_download_public_route.py) | Implementa `ProjectBackupDownloadPublicRouteTests`. |
| [`portal/tests/test_project_capabilities_catalog_parser.py`](../portal/tests/test_project_capabilities_catalog_parser.py) | Implementa `ProjectCapabilitiesCatalogParserTests`. |
| [`portal/tests/test_project_centered_navigation.py`](../portal/tests/test_project_centered_navigation.py) | Implementa `ProjectCenteredNavigationTest`. |
| [`portal/tests/test_project_config_active_reconciliation.py`](../portal/tests/test_project_config_active_reconciliation.py) | Implementa `ActiveProjectConfigurationReconciliationTests`. |
| [`portal/tests/test_project_config_controller_http.py`](../portal/tests/test_project_config_controller_http.py) | Implementa `ProjectConfigControllerHTTPTests`. |
| [`portal/tests/test_project_config_reconciler_behavior.py`](../portal/tests/test_project_config_reconciler_behavior.py) | Implementa `ProjectConfigReconcilerBehaviorTests`. |
| [`portal/tests/test_project_creation_modal_runtime.py`](../portal/tests/test_project_creation_modal_runtime.py) | Implementa `ProjectCreationModalRuntimeTest`. |
| [`portal/tests/test_project_creation_wizard_steps.py`](../portal/tests/test_project_creation_wizard_steps.py) | Implementa `ProjectCreationWizardStepsTest`. |
| [`portal/tests/test_project_delete_already_deleted_ui.py`](../portal/tests/test_project_delete_already_deleted_ui.py) | Implementa `ProjectDeleteAlreadyDeletedUITests`. |
| [`portal/tests/test_project_delete_cleans_derived_komodo_resources.py`](../portal/tests/test_project_delete_cleans_derived_komodo_resources.py) | Implementa `ProjectDeleteCleansDerivedKomodoResourcesTests`. |
| [`portal/tests/test_project_delete_confirmation_normalization.py`](../portal/tests/test_project_delete_confirmation_normalization.py) | Implementa `ProjectDeleteConfirmationNormalizationTests`. |
| [`portal/tests/test_project_delete_global_groups_and_polling.py`](../portal/tests/test_project_delete_global_groups_and_polling.py) | Implementa `ProjectDeleteGlobalGroupsAndPollingTests`. |
| [`portal/tests/test_project_delete_idempotent_cleanup.py`](../portal/tests/test_project_delete_idempotent_cleanup.py) | Implementa `ProjectDeleteIdempotentCleanupTests`. |
| [`portal/tests/test_project_delete_personal_forgejo_repo.py`](../portal/tests/test_project_delete_personal_forgejo_repo.py) | Implementa `ProjectDeletePersonalForgejoRepoTests`. |
| [`portal/tests/test_project_delete_tracking_modal.py`](../portal/tests/test_project_delete_tracking_modal.py) | Implementa `ProjectDeleteTrackingModalTests`. |
| [`portal/tests/test_project_delete_wizard_required.py`](../portal/tests/test_project_delete_wizard_required.py) | Implementa `ProjectDeleteWizardRequiredTests`. |
| [`portal/tests/test_project_environment_controller.py`](../portal/tests/test_project_environment_controller.py) | Implementa `load_module`, `ProjectEnvironmentControllerTests`. |
| [`portal/tests/test_project_environment_dotenv_contract.py`](../portal/tests/test_project_environment_dotenv_contract.py) | Implementa `load_module`, `ProjectEnvironmentDotenvContractTests`. |
| [`portal/tests/test_project_environment_effective_resolution.py`](../portal/tests/test_project_environment_effective_resolution.py) | Implementa `ProjectEnvironmentEffectiveResolutionTests`. |
| [`portal/tests/test_project_environment_mcp_contract.py`](../portal/tests/test_project_environment_mcp_contract.py) | Implementa `load_gateway`, `ProjectEnvironmentMCPContractTests`. |
| [`portal/tests/test_project_environment_secret_store.py`](../portal/tests/test_project_environment_secret_store.py) | Implementa `load_secret`, `ProjectEnvironmentSecretStoreTests`. |
| [`portal/tests/test_project_environment_web_api.py`](../portal/tests/test_project_environment_web_api.py) | Implementa `load_module`, `ProjectEnvironmentWebAPITests`. |
| [`portal/tests/test_project_environments_overview.py`](../portal/tests/test_project_environments_overview.py) | Implementa `load_module`, `ProjectEnvironmentsOverviewTests`. |
| [`portal/tests/test_project_manifest_controller.py`](../portal/tests/test_project_manifest_controller.py) | Implementa `ProjectManifestControllerTests`. |
| [`portal/tests/test_project_manifest_environment_toolchain_v1.py`](../portal/tests/test_project_manifest_environment_toolchain_v1.py) | Implementa `load_module`, `ProjectManifestEnvironmentToolchainV1Tests`. |
| [`portal/tests/test_project_observability_mcp_web.py`](../portal/tests/test_project_observability_mcp_web.py) | Implementa `load_web`, `load_gateway`, `ProjectObservabilityMCPWebTests`. |
| [`portal/tests/test_project_observability_service.py`](../portal/tests/test_project_observability_service.py) | Implementa `load_module`, `ProjectObservabilityServiceTests`. |
| [`portal/tests/test_project_owner_delete_authorization.py`](../portal/tests/test_project_owner_delete_authorization.py) | Implementa `load_module`, `ProjectOwnerDeleteAuthorizationTests`, `ProjectOwnerDeleteRouteContractTests`. |
| [`portal/tests/test_project_provision_resume_contract.py`](../portal/tests/test_project_provision_resume_contract.py) | Implementa `ProjectProvisionResumeContractTests`. |
| [`portal/tests/test_project_provision_status_recovery.py`](../portal/tests/test_project_provision_status_recovery.py) | Implementa `load_module`, `ProjectProvisionStatusRecoveryTests`. |
| [`portal/tests/test_project_provisioning_contract.py`](../portal/tests/test_project_provisioning_contract.py) | Implementa `ProjectProvisioningContractTest`. |
| [`portal/tests/test_project_provisioning_live_wizard.py`](../portal/tests/test_project_provisioning_live_wizard.py) | Implementa `ProjectProvisioningLiveWizardTests`. |
| [`portal/tests/test_project_publication_configuration_v1.py`](../portal/tests/test_project_publication_configuration_v1.py) | Implementa `load`, `ProjectPublicationConfigurationV1Tests`. |
| [`portal/tests/test_project_repo_oauth_owner.py`](../portal/tests/test_project_repo_oauth_owner.py) | Implementa `ProjectRepoOauthOwnerTests`. |
| [`portal/tests/test_project_repository_manual.py`](../portal/tests/test_project_repository_manual.py) | Implementa `ProjectRepositoryManualTests`. |
| [`portal/tests/test_project_resource_reorganization.py`](../portal/tests/test_project_resource_reorganization.py) | Implementa `ProjectResourceReorganizationTest`, `ActiveProjectRendererContractTest`, `DefinitiveProjectManagementRendererTest`. |
| [`portal/tests/test_project_runtime_reconciler_mcp_web.py`](../portal/tests/test_project_runtime_reconciler_mcp_web.py) | Implementa `load_web`, `load_gateway`, `ProjectRuntimeReconcilerMCPWebTests`. |
| [`portal/tests/test_project_runtime_reconciler_states.py`](../portal/tests/test_project_runtime_reconciler_states.py) | Implementa `load_module`, `ProjectRuntimeReconcilerStateTests`. |
| [`portal/tests/test_project_runtime_status_ui.py`](../portal/tests/test_project_runtime_status_ui.py) | Implementa `ProjectRuntimeStatusUITests`. |
| [`portal/tests/test_project_secret_controller_contract.py`](../portal/tests/test_project_secret_controller_contract.py) | Implementa `ProjectSecretControllerContractTests`. |
| [`portal/tests/test_project_secret_mcp_contract.py`](../portal/tests/test_project_secret_mcp_contract.py) | Implementa `load_gateway`, `ProjectSecretMCPContractTests`. |
| [`portal/tests/test_project_secret_web_api.py`](../portal/tests/test_project_secret_web_api.py) | Implementa `load_module`, `ProjectSecretWebAPITests`. |
| [`portal/tests/test_project_terminal_dedicated_flow.py`](../portal/tests/test_project_terminal_dedicated_flow.py) | Implementa `ProjectTerminalDedicatedFlowTests`. |
| [`portal/tests/test_project_toolchain_web_api.py`](../portal/tests/test_project_toolchain_web_api.py) | Implementa `load_module`, `ProjectToolchainWebAPITests`. |
| [`portal/tests/test_provision_worker_persists_forgejo_owner.py`](../portal/tests/test_provision_worker_persists_forgejo_owner.py) | Implementa `ProvisionWorkerPersistsForgejoOwnerTests`. |
| [`portal/tests/test_provision_worker_systemd_recovery.py`](../portal/tests/test_provision_worker_systemd_recovery.py) | Implementa `ProvisionWorkerSystemdRecoveryTest`. |
| [`portal/tests/test_provisioning_metadata_persistence_contract.py`](../portal/tests/test_provisioning_metadata_persistence_contract.py) | Implementa `ProvisioningMetadataPersistenceContractTest`. |
| [`portal/tests/test_provisioning_policy_readme_dark_theme.py`](../portal/tests/test_provisioning_policy_readme_dark_theme.py) | Implementa `ProvisioningPolicyReadmeDarkThemeTest`. |
| [`portal/tests/test_provisioning_runtime_completion_contract.py`](../portal/tests/test_provisioning_runtime_completion_contract.py) | Implementa `ProvisioningRuntimeCompletionContractTest`. |
| [`portal/tests/test_provisioning_waits_start_page_theme.py`](../portal/tests/test_provisioning_waits_start_page_theme.py) | Implementa `ProvisioningWaitsStartPageThemeTest`. |
| [`portal/tests/test_publication_deploy_promotion_race.py`](../portal/tests/test_publication_deploy_promotion_race.py) | Implementa `PublicationDeployPromotionRaceTests`. |
| [`portal/tests/test_publication_jobs.py`](../portal/tests/test_publication_jobs.py) | Implementa `PublicationJobsTest`. |
| [`portal/tests/test_publication_management_ui.py`](../portal/tests/test_publication_management_ui.py) | Implementa `PublicationManagementUITest`. |
| [`portal/tests/test_publication_personal_owner_base_project.py`](../portal/tests/test_publication_personal_owner_base_project.py) | Implementa `PublicationPersonalOwnerBaseProjectTests`. |
| [`portal/tests/test_publication_runtime_fallback.py`](../portal/tests/test_publication_runtime_fallback.py) | Implementa `PublicationRuntimeFallbackTest`. |
| [`portal/tests/test_publication_runtime_links_and_actions.py`](../portal/tests/test_publication_runtime_links_and_actions.py) | Implementa `PublicationRuntimeLinksAndActionsTests`. |
| [`portal/tests/test_publication_site_terminal_workspace.py`](../portal/tests/test_publication_site_terminal_workspace.py) | Implementa `PublicationSiteTerminalWorkspaceTests`. |
| [`portal/tests/test_publication_workspace_tools.py`](../portal/tests/test_publication_workspace_tools.py) | Implementa `PublicationWorkspaceToolsTests`. |
| [`portal/tests/test_recreate_owner_and_initial_terminal.py`](../portal/tests/test_recreate_owner_and_initial_terminal.py) | Implementa `RecreateOwnerAndInitialTerminalTests`. |
| [`portal/tests/test_registry.py`](../portal/tests/test_registry.py) | Implementa `_identity`, `_req`, `RegistryTest`. |
| [`portal/tests/test_release_flow_wizard_ui.py`](../portal/tests/test_release_flow_wizard_ui.py) | Implementa `ReleaseFlowWizardUITests`. |
| [`portal/tests/test_repository_readme_landing.py`](../portal/tests/test_repository_readme_landing.py) | Implementa `test_repository_uses_root_readme_as_github_landing_page`, `test_readme_visual_assets_exist_and_svg_is_valid`, `test_documentation_generator_does_not_recreate_shadow_readme`. |
| [`portal/tests/test_router_warmup_visual.py`](../portal/tests/test_router_warmup_visual.py) | Implementa `RouterWarmupVisualTests`. |
| [`portal/tests/test_runtime_cards_open_komodo.py`](../portal/tests/test_runtime_cards_open_komodo.py) | Implementa `RuntimeCardsOpenKomodoTests`. |
| [`portal/tests/test_runtime_completion_contract.py`](../portal/tests/test_runtime_completion_contract.py) | Implementa `RuntimeCompletionContractTest`. |
| [`portal/tests/test_runtime_diagnostics_new_tab.py`](../portal/tests/test_runtime_diagnostics_new_tab.py) | Implementa `RuntimeDiagnosticsNewTabTests`. |
| [`portal/tests/test_runtime_framework_inspection.py`](../portal/tests/test_runtime_framework_inspection.py) | Implementa `RuntimeFrameworkInspectionContractTest`. |
| [`portal/tests/test_runtime_info_active_publication.py`](../portal/tests/test_runtime_info_active_publication.py) | Implementa `RuntimeInfoActivePublicationTests`. |
| [`portal/tests/test_runtime_info_reconcile_retry.py`](../portal/tests/test_runtime_info_reconcile_retry.py) | Implementa `RuntimeInfoReconcileRetryTests`. |
| [`portal/tests/test_runtime_modal_body_layer.py`](../portal/tests/test_runtime_modal_body_layer.py) | Implementa `RuntimeModalBodyLayerTests`. |
| [`portal/tests/test_runtime_modal_web.py`](../portal/tests/test_runtime_modal_web.py) | Implementa `RuntimeModalWebTests`. |
| [`portal/tests/test_shared_user_related_stacks.py`](../portal/tests/test_shared_user_related_stacks.py) | Implementa `SharedUserRelatedStacksTests`. |
| [`portal/tests/test_shell_and_services.py`](../portal/tests/test_shell_and_services.py) | Shell rendering and per-module service unit tests (A5). |
| [`portal/tests/test_supabase_mcp_database_connector_contract.py`](../portal/tests/test_supabase_mcp_database_connector_contract.py) | Implementa `SupabaseMCPDatabaseConnectorContractTest`. |
| [`portal/tests/test_supabase_mcp_sql_policy.py`](../portal/tests/test_supabase_mcp_sql_policy.py) | Implementa `SupabaseMCPSQLPolicyTest`. |
| [`portal/tests/test_template_fileops_personal_owner.py`](../portal/tests/test_template_fileops_personal_owner.py) | Implementa `TemplateFileOpsPersonalOwnerTests`. |
| [`portal/tests/test_tenant_always_on_final_handler.py`](../portal/tests/test_tenant_always_on_final_handler.py) | Implementa `TenantAlwaysOnFinalHandlerTests`. |
| [`portal/tests/test_tenant_auto_off_and_countdown.py`](../portal/tests/test_tenant_auto_off_and_countdown.py) | Implementa `TenantAutoOffCountdownTests`. |
| [`portal/tests/test_tenant_backup_dynamic_and_graceful_tls.py`](../portal/tests/test_tenant_backup_dynamic_and_graceful_tls.py) | Implementa `TenantBackupAndTlsTests`. |
| [`portal/tests/test_tenant_delete_job_receipt.py`](../portal/tests/test_tenant_delete_job_receipt.py) | Implementa `TenantDeleteJobReceiptTests`. |
| [`portal/tests/test_tenant_guard_auto_recovery.py`](../portal/tests/test_tenant_guard_auto_recovery.py) | Implementa `load_module`, `TenantGuardAutoRecoveryTests`. |
| [`portal/tests/test_tenant_https_entry_contract.py`](../portal/tests/test_tenant_https_entry_contract.py) | Implementa `TenantHttpsEntryContractTest`. |
| [`portal/tests/test_tenant_port_allocator_contract.py`](../portal/tests/test_tenant_port_allocator_contract.py) | Implementa `TenantPortAllocatorContractTests`. |
| [`portal/tests/test_tenant_proxy_lifecycle_contract.py`](../portal/tests/test_tenant_proxy_lifecycle_contract.py) | Implementa `TenantProxyLifecycleContractTest`. |
| [`portal/tests/test_terminal_and_publication_layout.py`](../portal/tests/test_terminal_and_publication_layout.py) | Implementa `TerminalAndPublicationLayoutTests`. |
| [`portal/tests/test_terminal_reconciles_unified_stack.py`](../portal/tests/test_terminal_reconciles_unified_stack.py) | Implementa `TerminalReconcilesUnifiedStackTests`. |
| [`portal/tests/test_terminal_stack_resolution_contract.py`](../portal/tests/test_terminal_stack_resolution_contract.py) | Implementa `TerminalStackResolutionContractTest`. |
| [`portal/tests/test_terminal_uses_active_publication_stack.py`](../portal/tests/test_terminal_uses_active_publication_stack.py) | Implementa `TerminalUsesActivePublicationStackTests`. |
| [`portal/tests/test_terminal_uses_authenticated_actor.py`](../portal/tests/test_terminal_uses_authenticated_actor.py) | Implementa `TerminalUsesAuthenticatedActorTests`. |
| [`portal/tests/test_toolchain_catalog_policy.py`](../portal/tests/test_toolchain_catalog_policy.py) | Implementa `load`, `ToolchainCatalogPolicyTests`. |
| [`portal/tests/test_toolchain_lifecycle_broker.py`](../portal/tests/test_toolchain_lifecycle_broker.py) | Implementa `load_broker`, `ToolchainLifecycleBrokerTests`, `hashlib_sha`. |
| [`portal/tests/test_toolchain_mcp_contract.py`](../portal/tests/test_toolchain_mcp_contract.py) | Implementa `load_gateway`, `ToolchainMCPContractTests`. |
| [`portal/tests/test_ui_security_gate_contract.py`](../portal/tests/test_ui_security_gate_contract.py) | Implementa `UISecurityGateContractTests`. |
| [`portal/tests/test_unified_project_runtime.py`](../portal/tests/test_unified_project_runtime.py) | Implementa `UnifiedProjectRuntimeTests`. |
| [`portal/tests/test_unified_runtime_documentation.py`](../portal/tests/test_unified_runtime_documentation.py) | Implementa `UnifiedRuntimeDocumentationTests`. |
| [`portal/tests/test_user_owned_forgejo_and_komodo_acl.py`](../portal/tests/test_user_owned_forgejo_and_komodo_acl.py) | Implementa `UserOwnedForgejoAndKomodoAclTests`. |
| [`portal/tests/test_versioned_unified_runtime_publication.py`](../portal/tests/test_versioned_unified_runtime_publication.py) | Implementa `VersionedUnifiedRuntimePublicationTests`. |
| [`portal/tests/test_w_h_p_release_flow.py`](../portal/tests/test_w_h_p_release_flow.py) | Implementa `WHPReleaseFlowTests`. |
| [`portal/tests/test_workspace_artifact_direct_http.py`](../portal/tests/test_workspace_artifact_direct_http.py) | Implementa `WorkspaceArtifactDirectHTTPTests`. |
| [`portal/tests/test_workspace_artifact_direct_upload.py`](../portal/tests/test_workspace_artifact_direct_upload.py) | Implementa `WorkspaceArtifactDirectUploadTests`. |
| [`portal/tests/test_workspace_artifact_session_import.py`](../portal/tests/test_workspace_artifact_session_import.py) | Implementa `WorkspaceArtifactSessionImportTests`. |
| [`portal/tests/test_workspace_artifact_upload.py`](../portal/tests/test_workspace_artifact_upload.py) | Implementa `WorkspaceArtifactUploadTests`. |
| [`portal/tests/test_workspace_change_set.py`](../portal/tests/test_workspace_change_set.py) | Implementa `b64`, `WorkspaceChangeSetTests`. |
| [`portal/ui/README.md`](../portal/ui/README.md) | Documentação deste diretório. |
| [`portal/ui/__init__.py`](../portal/ui/__init__.py) | Portal v2 UI primitives. |
| [`portal/ui/components.py`](../portal/ui/components.py) | Semantic HTML primitives backed exclusively by portal/design. |
| [`portal/ui/icons.py`](../portal/ui/icons.py) | Inline SVG registry; add icons only when a migrated module needs them. |
| [`portal/ui/shell.py`](../portal/ui/shell.py) | Canonical CloudIFF Portal v2 shell |
| [`portal/wiring.py`](../portal/wiring.py) | Install every migrated module into the registry |
| [`scripts/README.md`](../scripts/README.md) | Documentação deste diretório. |
| [`scripts/generate-directory-readmes.py`](../scripts/generate-directory-readmes.py) | Implementa `tracked_paths`, `title_for`, `py_summary`, `file_summary`, `dir_summary`, `update_readme` e outros componentes. |
| [`scripts/generate-technical-catalogs.py`](../scripts/generate-technical-catalogs.py) | Implementa `esc`, `service_catalog`, `route_catalog`, `agents_catalog`, `extract_create_table_snippet`, `schema_catalog`. |
| [`scripts/test.sh`](../scripts/test.sh) | Automação Shell operacional da plataforma. |
| [`scripts/validate-repository.py`](../scripts/validate-repository.py) | Offline integrity and secret validation for the CloudIFF source repository. |
| [`scripts/validate.sh`](../scripts/validate.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/README.md`](../tenant-templates/README.md) | Documentação deste diretório. |
| [`tenant-templates/srv/README.md`](../tenant-templates/srv/README.md) | Documentação deste diretório. |
| [`tenant-templates/srv/cloudif/README.md`](../tenant-templates/srv/cloudif/README.md) | Documentação deste diretório. |
| [`tenant-templates/srv/cloudif/tenants/README.md`](../tenant-templates/srv/cloudif/tenants/README.md) | Documentação deste diretório. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/.gitattributes`](../tenant-templates/srv/cloudif/tenants/akadmin/.gitattributes) | Arquivo de suporte da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/.gitignore`](../tenant-templates/srv/cloudif/tenants/akadmin/.gitignore) | Arquivo de suporte da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/CHANGELOG.md`](../tenant-templates/srv/cloudif/tenants/akadmin/CHANGELOG.md) | Documento técnico ou operacional. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/CONFIG.md`](../tenant-templates/srv/cloudif/tenants/akadmin/CONFIG.md) | Documento técnico ou operacional. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/README.md`](../tenant-templates/srv/cloudif/tenants/akadmin/README.md) | Documentação deste diretório. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/db:54330`](../tenant-templates/srv/cloudif/tenants/akadmin/db:54330) | Arquivo de suporte da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/dev/README.md`](../tenant-templates/srv/cloudif/tenants/akadmin/dev/README.md) | Documentação deste diretório. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/dev/docker-compose.dev.yml`](../tenant-templates/srv/cloudif/tenants/akadmin/dev/docker-compose.dev.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/docker-compose.caddy.yml`](../tenant-templates/srv/cloudif/tenants/akadmin/docker-compose.caddy.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/docker-compose.envoy.yml`](../tenant-templates/srv/cloudif/tenants/akadmin/docker-compose.envoy.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/docker-compose.logs.yml`](../tenant-templates/srv/cloudif/tenants/akadmin/docker-compose.logs.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/docker-compose.nginx.yml`](../tenant-templates/srv/cloudif/tenants/akadmin/docker-compose.nginx.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/docker-compose.pg17.yml`](../tenant-templates/srv/cloudif/tenants/akadmin/docker-compose.pg17.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/docker-compose.rustfs.yml`](../tenant-templates/srv/cloudif/tenants/akadmin/docker-compose.rustfs.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/docker-compose.s3.yml`](../tenant-templates/srv/cloudif/tenants/akadmin/docker-compose.s3.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/docker-compose.yml`](../tenant-templates/srv/cloudif/tenants/akadmin/docker-compose.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/reset.sh`](../tenant-templates/srv/cloudif/tenants/akadmin/reset.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/run.sh`](../tenant-templates/srv/cloudif/tenants/akadmin/run.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/setup.sh`](../tenant-templates/srv/cloudif/tenants/akadmin/setup.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/tests/README.md`](../tenant-templates/srv/cloudif/tenants/akadmin/tests/README.md) | Documentação deste diretório. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/tests/docker-compose.rustfs.test.yml`](../tenant-templates/srv/cloudif/tenants/akadmin/tests/docker-compose.rustfs.test.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/tests/docker-compose.s3.test.yml`](../tenant-templates/srv/cloudif/tenants/akadmin/tests/docker-compose.s3.test.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/tests/test-auth-keys.sh`](../tenant-templates/srv/cloudif/tenants/akadmin/tests/test-auth-keys.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/tests/test-container-logs.sh`](../tenant-templates/srv/cloudif/tenants/akadmin/tests/test-container-logs.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/tests/test-pg17-upgrade.sh`](../tenant-templates/srv/cloudif/tenants/akadmin/tests/test-pg17-upgrade.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/tests/test-s3-backend.sh`](../tenant-templates/srv/cloudif/tenants/akadmin/tests/test-s3-backend.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/tests/test-s3.sh`](../tenant-templates/srv/cloudif/tenants/akadmin/tests/test-s3.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/tests/test-self-hosted.sh`](../tenant-templates/srv/cloudif/tenants/akadmin/tests/test-self-hosted.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/utils/README.md`](../tenant-templates/srv/cloudif/tenants/akadmin/utils/README.md) | Documentação deste diretório. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/utils/add-new-auth-keys.sh`](../tenant-templates/srv/cloudif/tenants/akadmin/utils/add-new-auth-keys.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/utils/db-passwd.sh`](../tenant-templates/srv/cloudif/tenants/akadmin/utils/db-passwd.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/utils/generate-keys.sh`](../tenant-templates/srv/cloudif/tenants/akadmin/utils/generate-keys.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/utils/reassign-owner.sh`](../tenant-templates/srv/cloudif/tenants/akadmin/utils/reassign-owner.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/utils/rotate-new-api-keys.sh`](../tenant-templates/srv/cloudif/tenants/akadmin/utils/rotate-new-api-keys.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/utils/upgrade-pg17.sh`](../tenant-templates/srv/cloudif/tenants/akadmin/utils/upgrade-pg17.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/akadmin/versions.md`](../tenant-templates/srv/cloudif/tenants/akadmin/versions.md) | Documento técnico ou operacional. |
| [`tenant-templates/srv/cloudif/tenants/aluno/.gitattributes`](../tenant-templates/srv/cloudif/tenants/aluno/.gitattributes) | Arquivo de suporte da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/aluno/.gitignore`](../tenant-templates/srv/cloudif/tenants/aluno/.gitignore) | Arquivo de suporte da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/aluno/CHANGELOG.md`](../tenant-templates/srv/cloudif/tenants/aluno/CHANGELOG.md) | Documento técnico ou operacional. |
| [`tenant-templates/srv/cloudif/tenants/aluno/CONFIG.md`](../tenant-templates/srv/cloudif/tenants/aluno/CONFIG.md) | Documento técnico ou operacional. |
| [`tenant-templates/srv/cloudif/tenants/aluno/README.md`](../tenant-templates/srv/cloudif/tenants/aluno/README.md) | Documentação deste diretório. |
| [`tenant-templates/srv/cloudif/tenants/aluno/dev/README.md`](../tenant-templates/srv/cloudif/tenants/aluno/dev/README.md) | Documentação deste diretório. |
| [`tenant-templates/srv/cloudif/tenants/aluno/dev/docker-compose.dev.yml`](../tenant-templates/srv/cloudif/tenants/aluno/dev/docker-compose.dev.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/aluno/docker-compose.caddy.yml`](../tenant-templates/srv/cloudif/tenants/aluno/docker-compose.caddy.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/aluno/docker-compose.envoy.yml`](../tenant-templates/srv/cloudif/tenants/aluno/docker-compose.envoy.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/aluno/docker-compose.logs.yml`](../tenant-templates/srv/cloudif/tenants/aluno/docker-compose.logs.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/aluno/docker-compose.nginx.yml`](../tenant-templates/srv/cloudif/tenants/aluno/docker-compose.nginx.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/aluno/docker-compose.pg17.yml`](../tenant-templates/srv/cloudif/tenants/aluno/docker-compose.pg17.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/aluno/docker-compose.rustfs.yml`](../tenant-templates/srv/cloudif/tenants/aluno/docker-compose.rustfs.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/aluno/docker-compose.s3.yml`](../tenant-templates/srv/cloudif/tenants/aluno/docker-compose.s3.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/aluno/docker-compose.yml`](../tenant-templates/srv/cloudif/tenants/aluno/docker-compose.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/aluno/reset.sh`](../tenant-templates/srv/cloudif/tenants/aluno/reset.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/aluno/run.sh`](../tenant-templates/srv/cloudif/tenants/aluno/run.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/aluno/setup.sh`](../tenant-templates/srv/cloudif/tenants/aluno/setup.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/aluno/tests/README.md`](../tenant-templates/srv/cloudif/tenants/aluno/tests/README.md) | Documentação deste diretório. |
| [`tenant-templates/srv/cloudif/tenants/aluno/tests/docker-compose.rustfs.test.yml`](../tenant-templates/srv/cloudif/tenants/aluno/tests/docker-compose.rustfs.test.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/aluno/tests/docker-compose.s3.test.yml`](../tenant-templates/srv/cloudif/tenants/aluno/tests/docker-compose.s3.test.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/aluno/tests/test-auth-keys.sh`](../tenant-templates/srv/cloudif/tenants/aluno/tests/test-auth-keys.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/aluno/tests/test-container-logs.sh`](../tenant-templates/srv/cloudif/tenants/aluno/tests/test-container-logs.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/aluno/tests/test-pg17-upgrade.sh`](../tenant-templates/srv/cloudif/tenants/aluno/tests/test-pg17-upgrade.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/aluno/tests/test-s3-backend.sh`](../tenant-templates/srv/cloudif/tenants/aluno/tests/test-s3-backend.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/aluno/tests/test-s3.sh`](../tenant-templates/srv/cloudif/tenants/aluno/tests/test-s3.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/aluno/tests/test-self-hosted.sh`](../tenant-templates/srv/cloudif/tenants/aluno/tests/test-self-hosted.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/aluno/utils/README.md`](../tenant-templates/srv/cloudif/tenants/aluno/utils/README.md) | Documentação deste diretório. |
| [`tenant-templates/srv/cloudif/tenants/aluno/utils/add-new-auth-keys.sh`](../tenant-templates/srv/cloudif/tenants/aluno/utils/add-new-auth-keys.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/aluno/utils/db-passwd.sh`](../tenant-templates/srv/cloudif/tenants/aluno/utils/db-passwd.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/aluno/utils/generate-keys.sh`](../tenant-templates/srv/cloudif/tenants/aluno/utils/generate-keys.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/aluno/utils/reassign-owner.sh`](../tenant-templates/srv/cloudif/tenants/aluno/utils/reassign-owner.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/aluno/utils/rotate-new-api-keys.sh`](../tenant-templates/srv/cloudif/tenants/aluno/utils/rotate-new-api-keys.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/aluno/utils/upgrade-pg17.sh`](../tenant-templates/srv/cloudif/tenants/aluno/utils/upgrade-pg17.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/aluno/versions.md`](../tenant-templates/srv/cloudif/tenants/aluno/versions.md) | Documento técnico ou operacional. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/.gitattributes`](../tenant-templates/srv/cloudif/tenants/iff1742962/.gitattributes) | Arquivo de suporte da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/.gitignore`](../tenant-templates/srv/cloudif/tenants/iff1742962/.gitignore) | Arquivo de suporte da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/CHANGELOG.md`](../tenant-templates/srv/cloudif/tenants/iff1742962/CHANGELOG.md) | Documento técnico ou operacional. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/CONFIG.md`](../tenant-templates/srv/cloudif/tenants/iff1742962/CONFIG.md) | Documento técnico ou operacional. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/README.md`](../tenant-templates/srv/cloudif/tenants/iff1742962/README.md) | Documentação deste diretório. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/dev/README.md`](../tenant-templates/srv/cloudif/tenants/iff1742962/dev/README.md) | Documentação deste diretório. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/dev/docker-compose.dev.yml`](../tenant-templates/srv/cloudif/tenants/iff1742962/dev/docker-compose.dev.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/docker-compose.caddy.yml`](../tenant-templates/srv/cloudif/tenants/iff1742962/docker-compose.caddy.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/docker-compose.envoy.yml`](../tenant-templates/srv/cloudif/tenants/iff1742962/docker-compose.envoy.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/docker-compose.logs.yml`](../tenant-templates/srv/cloudif/tenants/iff1742962/docker-compose.logs.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/docker-compose.nginx.yml`](../tenant-templates/srv/cloudif/tenants/iff1742962/docker-compose.nginx.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/docker-compose.pg17.yml`](../tenant-templates/srv/cloudif/tenants/iff1742962/docker-compose.pg17.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/docker-compose.rustfs.yml`](../tenant-templates/srv/cloudif/tenants/iff1742962/docker-compose.rustfs.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/docker-compose.s3.yml`](../tenant-templates/srv/cloudif/tenants/iff1742962/docker-compose.s3.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/docker-compose.yml`](../tenant-templates/srv/cloudif/tenants/iff1742962/docker-compose.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/reset.sh`](../tenant-templates/srv/cloudif/tenants/iff1742962/reset.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/run.sh`](../tenant-templates/srv/cloudif/tenants/iff1742962/run.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/setup.sh`](../tenant-templates/srv/cloudif/tenants/iff1742962/setup.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/tests/README.md`](../tenant-templates/srv/cloudif/tenants/iff1742962/tests/README.md) | Documentação deste diretório. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/tests/docker-compose.rustfs.test.yml`](../tenant-templates/srv/cloudif/tenants/iff1742962/tests/docker-compose.rustfs.test.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/tests/docker-compose.s3.test.yml`](../tenant-templates/srv/cloudif/tenants/iff1742962/tests/docker-compose.s3.test.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/tests/test-auth-keys.sh`](../tenant-templates/srv/cloudif/tenants/iff1742962/tests/test-auth-keys.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/tests/test-container-logs.sh`](../tenant-templates/srv/cloudif/tenants/iff1742962/tests/test-container-logs.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/tests/test-pg17-upgrade.sh`](../tenant-templates/srv/cloudif/tenants/iff1742962/tests/test-pg17-upgrade.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/tests/test-s3-backend.sh`](../tenant-templates/srv/cloudif/tenants/iff1742962/tests/test-s3-backend.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/tests/test-s3.sh`](../tenant-templates/srv/cloudif/tenants/iff1742962/tests/test-s3.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/tests/test-self-hosted.sh`](../tenant-templates/srv/cloudif/tenants/iff1742962/tests/test-self-hosted.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/utils/README.md`](../tenant-templates/srv/cloudif/tenants/iff1742962/utils/README.md) | Documentação deste diretório. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/utils/add-new-auth-keys.sh`](../tenant-templates/srv/cloudif/tenants/iff1742962/utils/add-new-auth-keys.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/utils/db-passwd.sh`](../tenant-templates/srv/cloudif/tenants/iff1742962/utils/db-passwd.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/utils/generate-keys.sh`](../tenant-templates/srv/cloudif/tenants/iff1742962/utils/generate-keys.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/utils/reassign-owner.sh`](../tenant-templates/srv/cloudif/tenants/iff1742962/utils/reassign-owner.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/utils/rotate-new-api-keys.sh`](../tenant-templates/srv/cloudif/tenants/iff1742962/utils/rotate-new-api-keys.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/utils/upgrade-pg17.sh`](../tenant-templates/srv/cloudif/tenants/iff1742962/utils/upgrade-pg17.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1742962/versions.md`](../tenant-templates/srv/cloudif/tenants/iff1742962/versions.md) | Documento técnico ou operacional. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/.gitattributes`](../tenant-templates/srv/cloudif/tenants/iff1860746/.gitattributes) | Arquivo de suporte da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/.gitignore`](../tenant-templates/srv/cloudif/tenants/iff1860746/.gitignore) | Arquivo de suporte da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/CHANGELOG.md`](../tenant-templates/srv/cloudif/tenants/iff1860746/CHANGELOG.md) | Documento técnico ou operacional. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/CONFIG.md`](../tenant-templates/srv/cloudif/tenants/iff1860746/CONFIG.md) | Documento técnico ou operacional. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/README.md`](../tenant-templates/srv/cloudif/tenants/iff1860746/README.md) | Documentação deste diretório. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/dev/README.md`](../tenant-templates/srv/cloudif/tenants/iff1860746/dev/README.md) | Documentação deste diretório. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/dev/docker-compose.dev.yml`](../tenant-templates/srv/cloudif/tenants/iff1860746/dev/docker-compose.dev.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/docker-compose.caddy.yml`](../tenant-templates/srv/cloudif/tenants/iff1860746/docker-compose.caddy.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/docker-compose.envoy.yml`](../tenant-templates/srv/cloudif/tenants/iff1860746/docker-compose.envoy.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/docker-compose.logs.yml`](../tenant-templates/srv/cloudif/tenants/iff1860746/docker-compose.logs.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/docker-compose.nginx.yml`](../tenant-templates/srv/cloudif/tenants/iff1860746/docker-compose.nginx.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/docker-compose.pg17.yml`](../tenant-templates/srv/cloudif/tenants/iff1860746/docker-compose.pg17.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/docker-compose.rustfs.yml`](../tenant-templates/srv/cloudif/tenants/iff1860746/docker-compose.rustfs.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/docker-compose.s3.yml`](../tenant-templates/srv/cloudif/tenants/iff1860746/docker-compose.s3.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/docker-compose.yml`](../tenant-templates/srv/cloudif/tenants/iff1860746/docker-compose.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/reset.sh`](../tenant-templates/srv/cloudif/tenants/iff1860746/reset.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/run.sh`](../tenant-templates/srv/cloudif/tenants/iff1860746/run.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/setup.sh`](../tenant-templates/srv/cloudif/tenants/iff1860746/setup.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/tests/README.md`](../tenant-templates/srv/cloudif/tenants/iff1860746/tests/README.md) | Documentação deste diretório. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/tests/docker-compose.rustfs.test.yml`](../tenant-templates/srv/cloudif/tenants/iff1860746/tests/docker-compose.rustfs.test.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/tests/docker-compose.s3.test.yml`](../tenant-templates/srv/cloudif/tenants/iff1860746/tests/docker-compose.s3.test.yml) | Definição declarativa de serviços Docker Compose. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/tests/test-auth-keys.sh`](../tenant-templates/srv/cloudif/tenants/iff1860746/tests/test-auth-keys.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/tests/test-container-logs.sh`](../tenant-templates/srv/cloudif/tenants/iff1860746/tests/test-container-logs.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/tests/test-pg17-upgrade.sh`](../tenant-templates/srv/cloudif/tenants/iff1860746/tests/test-pg17-upgrade.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/tests/test-s3-backend.sh`](../tenant-templates/srv/cloudif/tenants/iff1860746/tests/test-s3-backend.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/tests/test-s3.sh`](../tenant-templates/srv/cloudif/tenants/iff1860746/tests/test-s3.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/tests/test-self-hosted.sh`](../tenant-templates/srv/cloudif/tenants/iff1860746/tests/test-self-hosted.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/utils/README.md`](../tenant-templates/srv/cloudif/tenants/iff1860746/utils/README.md) | Documentação deste diretório. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/utils/add-new-auth-keys.sh`](../tenant-templates/srv/cloudif/tenants/iff1860746/utils/add-new-auth-keys.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/utils/db-passwd.sh`](../tenant-templates/srv/cloudif/tenants/iff1860746/utils/db-passwd.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/utils/generate-keys.sh`](../tenant-templates/srv/cloudif/tenants/iff1860746/utils/generate-keys.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/utils/reassign-owner.sh`](../tenant-templates/srv/cloudif/tenants/iff1860746/utils/reassign-owner.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/utils/rotate-new-api-keys.sh`](../tenant-templates/srv/cloudif/tenants/iff1860746/utils/rotate-new-api-keys.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/utils/upgrade-pg17.sh`](../tenant-templates/srv/cloudif/tenants/iff1860746/utils/upgrade-pg17.sh) | Automação Shell operacional da plataforma. |
| [`tenant-templates/srv/cloudif/tenants/iff1860746/versions.md`](../tenant-templates/srv/cloudif/tenants/iff1860746/versions.md) | Documento técnico ou operacional. |
