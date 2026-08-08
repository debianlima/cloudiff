# Sbin

Componentes implantados no plano de controle e no host de hospedagem.

<!-- CLOUDIFF-AUTO-DOC:BEGIN -->

## Inventário automático de `components/control-plane/usr/local/sbin`

Componentes implantados no plano de controle e no host de hospedagem.

| Item | Tipo | Finalidade |
|---|---|---|
| [`cloudif-admin-portal.py`](cloudif-admin-portal.py) | `.py` | Implementa `now_iso`, `h`, `norm`, `slugify`, `parse_groups`, `db` e outros componentes. |
| [`cloudif-agent-pki.py`](cloudif-agent-pki.py) | `.py` | Implementa `now`, `run`, `audit`, `refresh_crls`, `create_token`, `enroll` e outros componentes. |
| [`cloudif-authz-gate.py`](cloudif-authz-gate.py) | `.py` | Implementa `NoRedirect`, `clean_host`, `tenant_from_request`, `groups_to_set`, `load_tenant_access`, `authorize_tenant` e outros componentes. |
| [`cloudif-certificate-alert-dispatcher.py`](cloudif-certificate-alert-dispatcher.py) | `.py` | Implementa `utcnow`, `iso`, `parse`, `env`, `should_dispatch`, `main`. |
| [`cloudif-config-backup.sh`](cloudif-config-backup.sh) | `.sh` | Script Shell de backup, retenção ou sincronização. |
| [`cloudif-control-plane-api.py`](cloudif-control-plane-api.py) | `.py` | Implementa `rows`, `H`. |
| [`cloudif-control-plane-integrity.py`](cloudif-control-plane-integrity.py) | `.py` | Implementa `now`, `digest`, `metadata`, `generate`, `check`. |
| [`cloudif-control-plane-smoke.py`](cloudif-control-plane-smoke.py) | `.py` | Implementa `env`, `http`. |
| [`cloudif-control-plane-sync.py`](cloudif-control-plane-sync.py) | `.py` | Módulo Python da plataforma. |
| [`cloudif-controller-certificate-renew.sh`](cloudif-controller-certificate-renew.sh) | `.sh` | Automação Shell operacional da plataforma. |
| [`cloudif-data-retention.py`](cloudif-data-retention.py) | `.py` | Implementa `clean_db`, `protected_clients`, `cleanup_temp_clients`. |
| [`cloudif-deploy-panel.py`](cloudif-deploy-panel.py) | `.py` | Implementa `now`, `ensure_db`, `db_exec`, `db_one`, `db_all`, `h` e outros componentes. |
| [`cloudif-firewall-8099.sh`](cloudif-firewall-8099.sh) | `.sh` | Automação Shell operacional da plataforma. |
| [`cloudif-harden-router-8099.sh`](cloudif-harden-router-8099.sh) | `.sh` | Script Shell que renderiza, valida ou recarrega rotas. |
| [`cloudif-healthcheck.sh`](cloudif-healthcheck.sh) | `.sh` | Automação Shell operacional da plataforma. |
| [`cloudif-input-firewall.sh`](cloudif-input-firewall.sh) | `.sh` | Automação Shell operacional da plataforma. |
| [`cloudif-inventario-oficial.sh`](cloudif-inventario-oficial.sh) | `.sh` | Automação Shell operacional da plataforma. |
| [`cloudif-logrotate-verify.sh`](cloudif-logrotate-verify.sh) | `.sh` | Automação Shell operacional da plataforma. |
| [`cloudif-machine-admin-db-backup.sh`](cloudif-machine-admin-db-backup.sh) | `.sh` | Script Shell de backup, retenção ou sincronização. |
| [`cloudif-machine-admin-dr-backup.sh`](cloudif-machine-admin-dr-backup.sh) | `.sh` | Script Shell de backup, retenção ou sincronização. |
| [`cloudif-machine-admin-dr-restore-test.sh`](cloudif-machine-admin-dr-restore-test.sh) | `.sh` | Script Shell de restauração ou teste de recuperação. |
| [`cloudif-machine-admin-dr-restore-validation.sh`](cloudif-machine-admin-dr-restore-validation.sh) | `.sh` | Script Shell de restauração ou teste de recuperação. |
| [`cloudif-machine-controller.py`](cloudif-machine-controller.py) | `.py` | Implementa `now`, `con`, `init`, `verify`, `process_certificates`, `upsert_inventory` e outros componentes. |
| [`cloudif-machine-executor.py`](cloudif-machine-executor.py) | `.py` | Módulo Python da plataforma. |
| [`cloudif-machine-guardian.py`](cloudif-machine-guardian.py) | `.py` | Implementa `send`, `main`. |
| [`cloudif-machine-harvester.py`](cloudif-machine-harvester.py) | `.py` | Implementa `verify_policy_envelope`, `controller_open`, `run`, `ensure_identity`, `cert_state`, `cert_record` e outros componentes. |
| [`cloudif-monthly-restore-test.sh`](cloudif-monthly-restore-test.sh) | `.sh` | Script Shell de restauração ou teste de recuperação. |
| [`cloudif-node-metrics.py`](cloudif-node-metrics.py) | `.py` | Implementa `run`, `network_summary`, `docker_summary`, `metrics`, `H`. |
| [`cloudif-patch-async-launch-route.sh`](cloudif-patch-async-launch-route.sh) | `.sh` | Automação Shell operacional da plataforma. |
| [`cloudif-patch-launch-route-v2.sh`](cloudif-patch-launch-route-v2.sh) | `.sh` | Automação Shell operacional da plataforma. |
| [`cloudif-patch-launch-route.sh`](cloudif-patch-launch-route.sh) | `.sh` | Automação Shell operacional da plataforma. |
| [`cloudif-patch-supabase-root-api.sh`](cloudif-patch-supabase-root-api.sh) | `.sh` | Automação Shell operacional da plataforma. |
| [`cloudif-patch-supabase-router.sh`](cloudif-patch-supabase-router.sh) | `.sh` | Script Shell que renderiza, valida ou recarrega rotas. |
| [`cloudif-portal-refresh-cache.py`](cloudif-portal-refresh-cache.py) | `.py` | Implementa `now_iso`, `db`, `init_db`, `fetch_json`, `network_rate`, `refresh_nodes` e outros componentes. |
| [`cloudif-portal-ttl-janitor.py`](cloudif-portal-ttl-janitor.py) | `.py` | Implementa `now`, `run`, `main`. |
| [`cloudif-project-backup-auto.py`](cloudif-project-backup-auto.py) | `.py` | Módulo Python da plataforma. |
| [`cloudif-project-backup-sync.sh`](cloudif-project-backup-sync.sh) | `.sh` | Script Shell de backup, retenção ou sincronização. |
| [`cloudif-project-backup.py`](cloudif-project-backup.py) | `.py` | Implementa `now`, `stamp`, `safe`, `load_state`, `save_state`, `db_rows` e outros componentes. |
| [`cloudif-project-ensure.py`](cloudif-project-ensure.py) | `.py` | Implementa `load_env_file`, `now`, `db`, `http_json`, `audit`, `save_project` e outros componentes. |
| [`cloudif-project-initial-publish.py`](cloudif-project-initial-publish.py) | `.py` | Implementa `envfile`, `request`, `public_number`, `next_recorded_deploy_number`, `immutable_deploy_conflict`, `project_access` e outros componentes. |
| [`cloudif-project-provision.sh`](cloudif-project-provision.sh) | `.sh` | Automação Shell operacional da plataforma. |
| [`cloudif-project-template-apply.py`](cloudif-project-template-apply.py) | `.py` | Implementa `read_env`, `post`, `public_number`, `build`, `project_readme`, `runtime_overlay` e outros componentes. |
| [`cloudif-project-template-seed.py`](cloudif-project-template-seed.py) | `.py` | Implementa `load_env`, `req`, `svg`, `files_for`, `seed_db`, `main`. |
| [`cloudif-publication-worker.py`](cloudif-publication-worker.py) | `.py` | Implementa `stop`. |
| [`cloudif-publish-1009-once.py`](cloudif-publish-1009-once.py) | `.py` | Módulo Python da plataforma. |
| [`cloudif-reconcile-tenant-certificates.py`](cloudif-reconcile-tenant-certificates.py) | `.py` | Implementa `tenants`, `main`. |
| [`cloudif-reconcile-worker.py`](cloudif-reconcile-worker.py) | `.py` | Implementa `read_env`, `forja_project`, `reconcile_project_runtime`, `db_container`, `internal_post`, `project_membership_snapshot` e outros componentes. |
| [`cloudif-refresh-komodo-status-cache.py`](cloudif-refresh-komodo-status-cache.py) | `.py` | Implementa `now_iso`, `add_seconds_iso`, `read_env`, `komodo_agent_config`, `http_json`, `ensure_table` e outros componentes. |
| [`cloudif-release-cycle`](cloudif-release-cycle) | `arquivo` | Arquivo de suporte da plataforma. |
| [`cloudif-release-dispatch.py`](cloudif-release-dispatch.py) | `.py` | Implementa `main`. |
| [`cloudif-release-maintenance`](cloudif-release-maintenance) | `arquivo` | Arquivo de suporte da plataforma. |
| [`cloudif-requeue-project-provision.sh`](cloudif-requeue-project-provision.sh) | `.sh` | Automação Shell operacional da plataforma. |
| [`cloudif-secure-release-gate.sh`](cloudif-secure-release-gate.sh) | `.sh` | Automação Shell operacional da plataforma. |
| [`cloudif-storage-guard.py`](cloudif-storage-guard.py) | `.py` | Implementa `usage`. |
| [`cloudif-supabase-launch-api.py`](cloudif-supabase-launch-api.py) | `.py` | Implementa `now`, `public_url`, `project_url`, `unit_name`, `state_file`, `log_file` e outros componentes. |
| [`cloudif-supabase-release-agent.py`](cloudif-supabase-release-agent.py) | `.py` | Implementa `authorized`, `safe_payload`, `validate_identity`, `inspect_tenant`, `backup`, `migrate` e outros componentes. |
| [`cloudif-supabase-session-broker.py`](cloudif-supabase-session-broker.py) | `.py` | Implementa `env`, `log`, `b64url`, `fetch_json`, `discovery`, `token_request` e outros componentes. |
| [`cloudif-tenant-db-backup-v2.sh`](cloudif-tenant-db-backup-v2.sh) | `.sh` | Script Shell de backup, retenção ou sincronização. |
| [`cloudif-tenant-db-backup.sh`](cloudif-tenant-db-backup.sh) | `.sh` | Script Shell de backup, retenção ou sincronização. |
| [`cloudif-tenant-ensure-bg.sh`](cloudif-tenant-ensure-bg.sh) | `.sh` | Script Shell de criação, manutenção ou reconciliação de tenant. |
| [`cloudif-tenant-guard.py`](cloudif-tenant-guard.py) | `.py` | Implementa `NoRedirect`, `log`, `clean_host`, `valid_tenant`, `tenant_from_request`, `env_value` e outros componentes. |
| [`cloudif-tenant-policy-ensure.py`](cloudif-tenant-policy-ensure.py) | `.py` | Apply and verify the initial availability policy of a newly-created tenant. |
| [`cloudif-test-cross-subdomain-publish-once.py`](cloudif-test-cross-subdomain-publish-once.py) | `.py` | Implementa `NR`. |
| [`cloudif-test-d2-deploy.sh`](cloudif-test-d2-deploy.sh) | `.sh` | Automação Shell operacional da plataforma. |
| [`cloudif-test-mobile-null-origin-publish-once.py`](cloudif-test-mobile-null-origin-publish-once.py) | `.py` | Implementa `NR`. |
| [`cloudif-test-publication-redirect-once.py`](cloudif-test-publication-redirect-once.py) | `.py` | Implementa `NoRedirect`. |
| [`cloudif-test-tenant-control-publish-once.py`](cloudif-test-tenant-control-publish-once.py) | `.py` | Implementa `NR`. |
| [`cloudif-test-tenant-publish-button-once.py`](cloudif-test-tenant-publish-button-once.py) | `.py` | Módulo Python da plataforma. |
| [`cloudif-ui-security-review-run.sh`](cloudif-ui-security-review-run.sh) | `.sh` | Automação Shell operacional da plataforma. |
| [`cloudif-workspace-cleanup.py`](cloudif-workspace-cleanup.py) | `.py` | Implementa `atomic_write`, `docker`, `main`. |

> Esta seção é gerada por `scripts/generate-directory-readmes.py`. Conteúdo manual fora dos marcadores é preservado.

<!-- CLOUDIFF-AUTO-DOC:END -->
