# Tests

Arquitetura modular, interface, configuração e testes do Portal.

<!-- CLOUDIFF-AUTO-DOC:BEGIN -->

## Inventário automático de `portal/tests`

Arquitetura modular, interface, configuração e testes do Portal.

| Item | Tipo | Finalidade |
|---|---|---|
| [`__init__.py`](__init__.py) | `.py` | Módulo Python da plataforma. |
| [`test_admin_delete_agent_integration_contract.py`](test_admin_delete_agent_integration_contract.py) | `.py` | Implementa `AdminDeleteAgentIntegrationContractTest`. |
| [`test_admin_delete_complete_resource_contract.py`](test_admin_delete_complete_resource_contract.py) | `.py` | Implementa `AdminDeleteCompleteResourceContractTest`. |
| [`test_admin_delete_identity_observability_contract.py`](test_admin_delete_identity_observability_contract.py) | `.py` | Implementa `AdminDeleteIdentityObservabilityContractTest`. |
| [`test_admin_project_delete_contract.py`](test_admin_project_delete_contract.py) | `.py` | Implementa `AdminProjectDeleteContractTest`. |
| [`test_admin_project_delete_runtime_contract.py`](test_admin_project_delete_runtime_contract.py) | `.py` | Implementa `AdminProjectDeleteRuntimeContractTest`. |
| [`test_ai_connectors_hub.py`](test_ai_connectors_hub.py) | `.py` | Implementa `AIConnectorsHubTests`. |
| [`test_concurrent_project_tenant_operations.py`](test_concurrent_project_tenant_operations.py) | `.py` | Implementa `ConcurrentProjectTenantOperationsTests`. |
| [`test_forgejo_webhook_automation_contract.py`](test_forgejo_webhook_automation_contract.py) | `.py` | Implementa `ForgejoWebhookAutomationContractTest`. |
| [`test_forja_komodo_client_unit_contract.py`](test_forja_komodo_client_unit_contract.py) | `.py` | Implementa `ForjaKomodoClientUnitContractTest`. |
| [`test_frozen_surfaces_contract.py`](test_frozen_surfaces_contract.py) | `.py` | Implementa `FrozenSurfacesContractTests`. |
| [`test_grouped_resources.py`](test_grouped_resources.py) | `.py` | Implementa `GroupedResourcesTest`, `IndividualPublicationTest`, `IndividualPublicationPresentationTest`. |
| [`test_initial_publication_readiness_contract.py`](test_initial_publication_readiness_contract.py) | `.py` | Implementa `InitialPublicationReadinessContractTest`. |
| [`test_komodo_destroy_completion_contract.py`](test_komodo_destroy_completion_contract.py) | `.py` | Implementa `KomodoDestroyCompletionContractTest`. |
| [`test_komodo_force_rebuild.py`](test_komodo_force_rebuild.py) | `.py` | Implementa `KomodoForceRebuildTests`. |
| [`test_legacy_shell.py`](test_legacy_shell.py) | `.py` | Implementa `LegacyShellTest`. |
| [`test_mcp_oauth_contract.py`](test_mcp_oauth_contract.py) | `.py` | Implementa `MCPOAuthContractTests`. |
| [`test_navigation_information_architecture.py`](test_navigation_information_architecture.py) | `.py` | Implementa `NavigationInformationArchitectureTest`. |
| [`test_node_php_mixed_runtime.py`](test_node_php_mixed_runtime.py) | `.py` | Implementa `NodePhpMixedRuntimeTests`. |
| [`test_overview_sites.py`](test_overview_sites.py) | `.py` | Implementa `OverviewSiteCardTest`. |
| [`test_permission_table.py`](test_permission_table.py) | `.py` | A2 acceptance: every migrated v2 guard decides exactly as the v1 table |
| [`test_platform_guide_canonical.py`](test_platform_guide_canonical.py) | `.py` | Implementa `CanonicalPlatformGuideTests`. |
| [`test_platform_guide_github.py`](test_platform_guide_github.py) | `.py` | Implementa `PlatformGuideGithubTests`. |
| [`test_project_centered_navigation.py`](test_project_centered_navigation.py) | `.py` | Implementa `ProjectCenteredNavigationTest`. |
| [`test_project_creation_modal_runtime.py`](test_project_creation_modal_runtime.py) | `.py` | Implementa `first_existing`, `ProjectCreationModalRuntimeTest`. |
| [`test_project_creation_wizard_steps.py`](test_project_creation_wizard_steps.py) | `.py` | Implementa `ProjectCreationWizardStepsTest`. |
| [`test_project_provisioning_contract.py`](test_project_provisioning_contract.py) | `.py` | Implementa `ProjectProvisioningContractTest`. |
| [`test_project_provisioning_live_wizard.py`](test_project_provisioning_live_wizard.py) | `.py` | Implementa `ProjectProvisioningLiveWizardTests`. |
| [`test_project_repository_manual.py`](test_project_repository_manual.py) | `.py` | Implementa `ProjectRepositoryManualTests`. |
| [`test_project_resource_reorganization.py`](test_project_resource_reorganization.py) | `.py` | Implementa `ProjectResourceReorganizationTest`, `ActiveProjectRendererContractTest`, `DefinitiveProjectManagementRendererTest`. |
| [`test_provisioning_metadata_persistence_contract.py`](test_provisioning_metadata_persistence_contract.py) | `.py` | Implementa `ProvisioningMetadataPersistenceContractTest`. |
| [`test_provisioning_runtime_completion_contract.py`](test_provisioning_runtime_completion_contract.py) | `.py` | Implementa `ProvisioningRuntimeCompletionContractTest`. |
| [`test_publication_jobs.py`](test_publication_jobs.py) | `.py` | Implementa `PublicationJobsTest`. |
| [`test_publication_management_ui.py`](test_publication_management_ui.py) | `.py` | Implementa `PublicationManagementUITest`. |
| [`test_publication_runtime_fallback.py`](test_publication_runtime_fallback.py) | `.py` | Implementa `PublicationRuntimeFallbackTest`. |
| [`test_registry.py`](test_registry.py) | `.py` | Implementa `_identity`, `_req`, `RegistryTest`. |
| [`test_runtime_completion_contract.py`](test_runtime_completion_contract.py) | `.py` | Implementa `RuntimeCompletionContractTest`. |
| [`test_runtime_framework_inspection.py`](test_runtime_framework_inspection.py) | `.py` | Implementa `RuntimeFrameworkInspectionContractTest`. |
| [`test_shell_and_services.py`](test_shell_and_services.py) | `.py` | Shell rendering and per-module service unit tests (A5). |
| [`test_tenant_delete_job_receipt.py`](test_tenant_delete_job_receipt.py) | `.py` | Implementa `TenantDeleteJobReceiptTests`. |
| [`test_terminal_stack_resolution_contract.py`](test_terminal_stack_resolution_contract.py) | `.py` | Implementa `TerminalStackResolutionContractTest`. |
| [`test_unified_project_runtime.py`](test_unified_project_runtime.py) | `.py` | Implementa `UnifiedProjectRuntimeTests`. |

> Esta seção é gerada por `scripts/generate-directory-readmes.py`. Conteúdo manual fora dos marcadores é preservado.

<!-- CLOUDIFF-AUTO-DOC:END -->
