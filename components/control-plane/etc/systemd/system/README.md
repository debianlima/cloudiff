# System

Componentes implantados no plano de controle e no host de hospedagem.

<!-- CLOUDIFF-AUTO-DOC:BEGIN -->

## Inventário automático de `components/control-plane/etc/systemd/system`

Componentes implantados no plano de controle e no host de hospedagem.

| Item | Tipo | Finalidade |
|---|---|---|
| [`cloudif-admin-portal.service.d/`](cloudif-admin-portal.service.d/) | Diretório | Componentes implantados no plano de controle e no host de hospedagem. |
| [`cloudif-authz-gate.service.d/`](cloudif-authz-gate.service.d/) | Diretório | Componentes implantados no plano de controle e no host de hospedagem. |
| [`cloudif-build-worker.service.d/`](cloudif-build-worker.service.d/) | Diretório | Componentes implantados no plano de controle e no host de hospedagem. |
| [`cloudif-deploy-panel.service.d/`](cloudif-deploy-panel.service.d/) | Diretório | Componentes implantados no plano de controle e no host de hospedagem. |
| [`cloudif-deployment-broker.service.d/`](cloudif-deployment-broker.service.d/) | Diretório | Componentes implantados no plano de controle e no host de hospedagem. |
| [`cloudif-node-metrics.service.d/`](cloudif-node-metrics.service.d/) | Diretório | Componentes implantados no plano de controle e no host de hospedagem. |
| [`cloudif-supabase-launch-api.service.d/`](cloudif-supabase-launch-api.service.d/) | Diretório | Componentes implantados no plano de controle e no host de hospedagem. |
| [`cloudif-supabase-session-broker.service.d/`](cloudif-supabase-session-broker.service.d/) | Diretório | Componentes implantados no plano de controle e no host de hospedagem. |
| [`cloudif-tenant-guard.service.d/`](cloudif-tenant-guard.service.d/) | Diretório | Componentes implantados no plano de controle e no host de hospedagem. |
| [`cloudif-academic-audit.service`](cloudif-academic-audit.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-admin-portal-staging.service`](cloudif-admin-portal-staging.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-admin-portal.service`](cloudif-admin-portal.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-agent-controller.path`](cloudif-agent-controller.path) | `.path` | Arquivo de suporte da plataforma. |
| [`cloudif-agent-controller.service`](cloudif-agent-controller.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-agent-controller.timer`](cloudif-agent-controller.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-agent-pki-crl-refresh.service`](cloudif-agent-pki-crl-refresh.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-agent-pki-crl-refresh.timer`](cloudif-agent-pki-crl-refresh.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-agent-registry.service`](cloudif-agent-registry.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-approval-api.service`](cloudif-approval-api.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-authz-gate.service`](cloudif-authz-gate.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-build-broker.service`](cloudif-build-broker.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-build-worker.service`](cloudif-build-worker.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-build-worker.timer`](cloudif-build-worker.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-certificate-alert-dispatcher.service`](cloudif-certificate-alert-dispatcher.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-certificate-alert-dispatcher.timer`](cloudif-certificate-alert-dispatcher.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-config-backup.service`](cloudif-config-backup.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-config-backup.timer`](cloudif-config-backup.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-control-dashboard.service`](cloudif-control-dashboard.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-control-plane-api.service`](cloudif-control-plane-api.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-control-plane-integrity.service`](cloudif-control-plane-integrity.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-control-plane-integrity.timer`](cloudif-control-plane-integrity.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-control-plane-smoke.service`](cloudif-control-plane-smoke.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-control-plane-smoke.timer`](cloudif-control-plane-smoke.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-control-plane-sync.service`](cloudif-control-plane-sync.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-control-plane-sync.timer`](cloudif-control-plane-sync.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-controller-certificate-renew.service`](cloudif-controller-certificate-renew.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-controller-certificate-renew.timer`](cloudif-controller-certificate-renew.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-data-retention.service`](cloudif-data-retention.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-data-retention.timer`](cloudif-data-retention.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-deploy-panel.service`](cloudif-deploy-panel.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-deployment-broker.service`](cloudif-deployment-broker.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-evaluation-api.service`](cloudif-evaluation-api.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-firewall-8099.service`](cloudif-firewall-8099.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-healthcheck.service`](cloudif-healthcheck.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-healthcheck.timer`](cloudif-healthcheck.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-input-firewall.service`](cloudif-input-firewall.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-logrotate-verify.service`](cloudif-logrotate-verify.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-logrotate-verify.timer`](cloudif-logrotate-verify.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-machine-admin-db-backup.service`](cloudif-machine-admin-db-backup.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-machine-admin-db-backup.timer`](cloudif-machine-admin-db-backup.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-machine-admin-dr-backup.service`](cloudif-machine-admin-dr-backup.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-machine-admin-dr-backup.timer`](cloudif-machine-admin-dr-backup.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-machine-admin-dr-restore-test.service`](cloudif-machine-admin-dr-restore-test.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-machine-admin-dr-restore-test.timer`](cloudif-machine-admin-dr-restore-test.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-machine-admin-dr-restore-validation.service`](cloudif-machine-admin-dr-restore-validation.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-machine-admin-dr-restore-validation.timer`](cloudif-machine-admin-dr-restore-validation.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-machine-controller.service`](cloudif-machine-controller.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-machine-guardian.service`](cloudif-machine-guardian.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-machine-guardian.timer`](cloudif-machine-guardian.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-machine-harvester.service`](cloudif-machine-harvester.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-machine-harvester.timer`](cloudif-machine-harvester.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-mcp-gateway.service`](cloudif-mcp-gateway.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-monitor-api.service`](cloudif-monitor-api.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-monitor-collector.service`](cloudif-monitor-collector.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-monitor-collector.timer`](cloudif-monitor-collector.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-monthly-restore-test.service`](cloudif-monthly-restore-test.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-monthly-restore-test.timer`](cloudif-monthly-restore-test.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-multiservice-preview-broker.service`](cloudif-multiservice-preview-broker.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-node-metrics.service`](cloudif-node-metrics.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-notification-api.service`](cloudif-notification-api.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-notification-evaluator.service`](cloudif-notification-evaluator.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-notification-evaluator.timer`](cloudif-notification-evaluator.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-portal-qa.service`](cloudif-portal-qa.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-portal-refresh-cache.service`](cloudif-portal-refresh-cache.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-portal-refresh-cache.timer`](cloudif-portal-refresh-cache.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-portal-ttl-janitor.service`](cloudif-portal-ttl-janitor.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-portal-ttl-janitor.timer`](cloudif-portal-ttl-janitor.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-preview-broker.service`](cloudif-preview-broker.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-preview-cleanup.service`](cloudif-preview-cleanup.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-preview-cleanup.timer`](cloudif-preview-cleanup.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-prod-ui-smoke.service`](cloudif-prod-ui-smoke.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-prod-ui-smoke.timer`](cloudif-prod-ui-smoke.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-production-window-guard.service`](cloudif-production-window-guard.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-production-window-guard.timer`](cloudif-production-window-guard.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-project-backup-auto.service`](cloudif-project-backup-auto.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-project-backup-auto.timer`](cloudif-project-backup-auto.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-project-backup.service`](cloudif-project-backup.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-project-backup.timer`](cloudif-project-backup.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-project-capabilities.path`](cloudif-project-capabilities.path) | `.path` | Arquivo de suporte da plataforma. |
| [`cloudif-project-capabilities.service`](cloudif-project-capabilities.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-project-capabilities.timer`](cloudif-project-capabilities.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-project-config-controller.service`](cloudif-project-config-controller.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-project-config-reconciler.service`](cloudif-project-config-reconciler.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-project-observability.service`](cloudif-project-observability.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-project-onboarding-reconcile.service`](cloudif-project-onboarding-reconcile.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-project-onboarding-reconcile.timer`](cloudif-project-onboarding-reconcile.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-project-onboarding.service`](cloudif-project-onboarding.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-project-provision-recover.service`](cloudif-project-provision-recover.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-project-provision-recover.timer`](cloudif-project-provision-recover.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-project-runtime-reconciler.service`](cloudif-project-runtime-reconciler.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-project-state-reconcile.path`](cloudif-project-state-reconcile.path) | `.path` | Arquivo de suporte da plataforma. |
| [`cloudif-project-state-reconcile.service`](cloudif-project-state-reconcile.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-project-state-reconcile.timer`](cloudif-project-state-reconcile.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-publication-worker.service`](cloudif-publication-worker.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-qa-ui-smoke.service`](cloudif-qa-ui-smoke.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-qa-ui-smoke.timer`](cloudif-qa-ui-smoke.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-reconcile-worker.path`](cloudif-reconcile-worker.path) | `.path` | Arquivo de suporte da plataforma. |
| [`cloudif-reconcile-worker.service`](cloudif-reconcile-worker.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-reconcile-worker.timer`](cloudif-reconcile-worker.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-release-dispatch.service`](cloudif-release-dispatch.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-release-dispatch.timer`](cloudif-release-dispatch.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-runtime-policy.service`](cloudif-runtime-policy.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-storage-guard.service`](cloudif-storage-guard.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-storage-guard.timer`](cloudif-storage-guard.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-supabase-launch-api.service`](cloudif-supabase-launch-api.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-supabase-mcp-broker.service`](cloudif-supabase-mcp-broker.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-supabase-onboarding-broker.service`](cloudif-supabase-onboarding-broker.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-supabase-release-agent.service`](cloudif-supabase-release-agent.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-supabase-session-broker.service`](cloudif-supabase-session-broker.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-tenant-certificate-reconcile.service`](cloudif-tenant-certificate-reconcile.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-tenant-certificate-reconcile.timer`](cloudif-tenant-certificate-reconcile.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-tenant-db-backup-v2.service`](cloudif-tenant-db-backup-v2.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-tenant-db-backup-v2.timer`](cloudif-tenant-db-backup-v2.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-tenant-db-backup.service`](cloudif-tenant-db-backup.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-tenant-db-backup.timer`](cloudif-tenant-db-backup.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-tenant-guard.service`](cloudif-tenant-guard.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-transaction-reconciler.service`](cloudif-transaction-reconciler.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-transaction-reconciler.timer`](cloudif-transaction-reconciler.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-ui-security-review.service`](cloudif-ui-security-review.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-ui-security-review.timer`](cloudif-ui-security-review.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-workspace-broker.service`](cloudif-workspace-broker.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-workspace-cleanup.service`](cloudif-workspace-cleanup.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-workspace-cleanup.timer`](cloudif-workspace-cleanup.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |

> Esta seção é gerada por `scripts/generate-directory-readmes.py`. Conteúdo manual fora dos marcadores é preservado.

<!-- CLOUDIFF-AUTO-DOC:END -->
