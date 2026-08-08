# Tests

Arquitetura modular, interface, configuração e testes do Portal.

<!-- CLOUDIFF-AUTO-DOC:BEGIN -->

## Inventário automático de `portal/tests`

Arquitetura modular, interface, configuração e testes do Portal.

| Item | Tipo | Finalidade |
|---|---|---|
| [`__init__.py`](__init__.py) | `.py` | Módulo Python da plataforma. |
| [`test_active_toolchain_consumption.py`](test_active_toolchain_consumption.py) | `.py` | Implementa `load`, `ActiveToolchainConsumptionTests`, `sqlite_connection`. |
| [`test_admin_delete_agent_integration_contract.py`](test_admin_delete_agent_integration_contract.py) | `.py` | Implementa `AdminDeleteAgentIntegrationContractTest`. |
| [`test_admin_delete_complete_resource_contract.py`](test_admin_delete_complete_resource_contract.py) | `.py` | Implementa `AdminDeleteCompleteResourceContractTest`. |
| [`test_admin_delete_identity_observability_contract.py`](test_admin_delete_identity_observability_contract.py) | `.py` | Implementa `AdminDeleteIdentityObservabilityContractTest`. |
| [`test_admin_project_delete_contract.py`](test_admin_project_delete_contract.py) | `.py` | Implementa `AdminProjectDeleteContractTest`. |
| [`test_admin_project_delete_runtime_contract.py`](test_admin_project_delete_runtime_contract.py) | `.py` | Implementa `AdminProjectDeleteRuntimeContractTest`. |
| [`test_ai_connectors_hub.py`](test_ai_connectors_hub.py) | `.py` | Implementa `AIConnectorsHubTests`. |
| [`test_approval_cancel.py`](test_approval_cancel.py) | `.py` | Implementa `load_api`, `ApprovalCancelTests`. |
| [`test_artifact_upload_agent_handoff.py`](test_artifact_upload_agent_handoff.py) | `.py` | Implementa `ArtifactUploadAgentHandoffTests`. |
| [`test_authz_gate_tenant_allowlist.py`](test_authz_gate_tenant_allowlist.py) | `.py` | Implementa `load_module`, `AuthzGateTenantAllowlistTests`. |
| [`test_backup_console_json_and_sections.py`](test_backup_console_json_and_sections.py) | `.py` | Implementa `BackupConsoleJsonAndSectionsTests`. |
| [`test_backup_progress_modal.py`](test_backup_progress_modal.py) | `.py` | Implementa `BackupProgressModalTests`. |
| [`test_backup_remote_global_config.py`](test_backup_remote_global_config.py) | `.py` | Implementa `BackupRemoteGlobalConfigTests`. |
| [`test_backup_role_visibility_policy.py`](test_backup_role_visibility_policy.py) | `.py` | Implementa `BackupRoleVisibilityPolicyTests`. |
| [`test_build_bound_preview_deployment_contract.py`](test_build_bound_preview_deployment_contract.py) | `.py` | Implementa `load_gateway`, `runtime_executor_path`, `BuildBoundPreviewDeploymentContractTests`. |
| [`test_canonical_help_videos.py`](test_canonical_help_videos.py) | `.py` | Implementa `CanonicalHelpVideosTests`. |
| [`test_change_set_argument_contract.py`](test_change_set_argument_contract.py) | `.py` | Implementa `load_module`, `ChangeSetArgumentContractTests`. |
| [`test_change_set_mcp_contract.py`](test_change_set_mcp_contract.py) | `.py` | Implementa `ChangeSetMCPContractTests`. |
| [`test_concurrent_project_tenant_operations.py`](test_concurrent_project_tenant_operations.py) | `.py` | Implementa `ConcurrentProjectTenantOperationsTests`. |
| [`test_connector_public_oauth_onboarding.py`](test_connector_public_oauth_onboarding.py) | `.py` | Implementa `ConnectorPublicOAuthOnboardingTest`. |
| [`test_dark_theme_legacy_surfaces.py`](test_dark_theme_legacy_surfaces.py) | `.py` | Implementa `DarkThemeLegacySurfacesTest`. |
| [`test_database_active_mode_fallback.py`](test_database_active_mode_fallback.py) | `.py` | Implementa `DatabaseActiveModeFallbackTests`. |
| [`test_deployment_sensitive_runtime_security.py`](test_deployment_sensitive_runtime_security.py) | `.py` | Implementa `load`, `DeploymentSecretInjectionSecurityTests`. |
| [`test_effective_environment_build_contract.py`](test_effective_environment_build_contract.py) | `.py` | Implementa `load_artifact`, `EffectiveEnvironmentBuildContractTests`. |
| [`test_forgejo_merge_sha_resolution.py`](test_forgejo_merge_sha_resolution.py) | `.py` | Implementa `FakeForgejo`, `forja_namespace`, `ForgejoMergeShaResolutionTests`. |
| [`test_forgejo_webhook_automation_contract.py`](test_forgejo_webhook_automation_contract.py) | `.py` | Implementa `ForgejoWebhookAutomationContractTest`. |
| [`test_forja_agent_only_provisioning.py`](test_forja_agent_only_provisioning.py) | `.py` | Implementa `ForjaAgentOnlyProvisioningTests`. |
| [`test_forja_change_set_proposal.py`](test_forja_change_set_proposal.py) | `.py` | Implementa `FakeForgejo`, `namespace`, `payload`, `ForjaChangeSetProposalTests`. |
| [`test_forja_komodo_client_unit_contract.py`](test_forja_komodo_client_unit_contract.py) | `.py` | Implementa `ForjaKomodoClientUnitContractTest`. |
| [`test_forja_personal_owner_and_komodo_payload.py`](test_forja_personal_owner_and_komodo_payload.py) | `.py` | Implementa `ForjaPersonalOwnerAndKomodoPayloadTests`. |
| [`test_frozen_surfaces_contract.py`](test_frozen_surfaces_contract.py) | `.py` | Implementa `FrozenSurfacesContractTests`. |
| [`test_grouped_resources.py`](test_grouped_resources.py) | `.py` | Implementa `GroupedResourcesTest`, `IndividualPublicationTest`, `IndividualPublicationPresentationTest`. |
| [`test_help_external_connections.py`](test_help_external_connections.py) | `.py` | Implementa `HelpExternalConnectionsTests`. |
| [`test_help_youtube_videos.py`](test_help_youtube_videos.py) | `.py` | Implementa `HelpYoutubeVideosTests`. |
| [`test_initial_publication_immutable_recovery.py`](test_initial_publication_immutable_recovery.py) | `.py` | Implementa `load_module`, `InitialPublicationImmutableRecoveryTests`. |
| [`test_initial_publication_local_health_fastpath.py`](test_initial_publication_local_health_fastpath.py) | `.py` | Implementa `InitialPublicationVersionedRuntimeTests`. |
| [`test_initial_publication_readiness_contract.py`](test_initial_publication_readiness_contract.py) | `.py` | Implementa `InitialPublicationReadinessContractTest`. |
| [`test_komodo_destroy_completion_contract.py`](test_komodo_destroy_completion_contract.py) | `.py` | Implementa `KomodoDestroyCompletionContractTest`. |
| [`test_komodo_force_rebuild.py`](test_komodo_force_rebuild.py) | `.py` | Implementa `KomodoForceRebuildTests`. |
| [`test_komodo_local_health_json.py`](test_komodo_local_health_json.py) | `.py` | Implementa `KomodoLocalHealthJsonTests`. |
| [`test_komodo_local_health_reconciliation.py`](test_komodo_local_health_reconciliation.py) | `.py` | Implementa `KomodoLocalHealthReconciliationTests`. |
| [`test_komodo_unified_layout_ensure.py`](test_komodo_unified_layout_ensure.py) | `.py` | Implementa `KomodoUnifiedLayoutEnsureTests`. |
| [`test_legacy_shell.py`](test_legacy_shell.py) | `.py` | Implementa `LegacyShellTest`. |
| [`test_mcp_actionable_error_contract.py`](test_mcp_actionable_error_contract.py) | `.py` | Implementa `load_gateway`, `MCPActionableErrorContractTests`. |
| [`test_mcp_documentation_catalog_parity.py`](test_mcp_documentation_catalog_parity.py) | `.py` | Implementa `load`, `MCPDocumentationCatalogParityTests`. |
| [`test_mcp_oauth_contract.py`](test_mcp_oauth_contract.py) | `.py` | Implementa `MCPOAuthContractTests`. |
| [`test_mcp_public_oauth_flow.py`](test_mcp_public_oauth_flow.py) | `.py` | Implementa `free_port`, `FakeControl`, `FakeAgent`, `MCPPublicOAuthFlowTest`. |
| [`test_membership_reconciliation.py`](test_membership_reconciliation.py) | `.py` | Implementa `MembershipReconciliationTests`. |
| [`test_multiservice_artifact_policy.py`](test_multiservice_artifact_policy.py) | `.py` | Implementa `MultiserviceArtifactPolicyTests`. |
| [`test_multiservice_build_broker.py`](test_multiservice_build_broker.py) | `.py` | Implementa `MultiserviceBuildBrokerTests`. |
| [`test_multiservice_build_mcp_contract.py`](test_multiservice_build_mcp_contract.py) | `.py` | Implementa `MultiserviceBuildMCPContractTests`. |
| [`test_multiservice_deployment_execution.py`](test_multiservice_deployment_execution.py) | `.py` | Implementa `load_module`, `MultiserviceDeploymentExecutionTests`. |
| [`test_multiservice_deployment_execution_mcp_contract.py`](test_multiservice_deployment_execution_mcp_contract.py) | `.py` | Implementa `MultiserviceDeploymentExecutionMCPContractTests`. |
| [`test_multiservice_deployment_executor.py`](test_multiservice_deployment_executor.py) | `.py` | Implementa `load_module`, `MultiserviceDeploymentExecutorTests`. |
| [`test_multiservice_deployment_mcp_contract.py`](test_multiservice_deployment_mcp_contract.py) | `.py` | Implementa `MultiserviceDeploymentMCPContractTests`. |
| [`test_multiservice_deployment_plan.py`](test_multiservice_deployment_plan.py) | `.py` | Implementa `load_module`, `MultiserviceDeploymentPlanTests`. |
| [`test_multiservice_preview_broker.py`](test_multiservice_preview_broker.py) | `.py` | Implementa `PreviewBrokerTests`. |
| [`test_multiservice_preview_executor.py`](test_multiservice_preview_executor.py) | `.py` | Implementa `PreviewExecutorTests`. |
| [`test_multiservice_preview_mcp_contract.py`](test_multiservice_preview_mcp_contract.py) | `.py` | Implementa `PreviewMCPContractTests`. |
| [`test_multiservice_runtime_config_contract.py`](test_multiservice_runtime_config_contract.py) | `.py` | Implementa `load_broker`, `MultiserviceRuntimeConfigContractTests`. |
| [`test_multitech_mcp_contract.py`](test_multitech_mcp_contract.py) | `.py` | Implementa `MultitechMCPContractTests`. |
| [`test_multitech_recursive_detector.py`](test_multitech_recursive_detector.py) | `.py` | Implementa `load_module`, `MultitechRecursiveDetectorTests`. |
| [`test_navigation_information_architecture.py`](test_navigation_information_architecture.py) | `.py` | Implementa `NavigationInformationArchitectureTest`. |
| [`test_node_php_mixed_runtime.py`](test_node_php_mixed_runtime.py) | `.py` | Implementa `NodePhpMixedRuntimeTests`. |
| [`test_overview_sites.py`](test_overview_sites.py) | `.py` | Implementa `OverviewSiteCardTest`. |
| [`test_permission_table.py`](test_permission_table.py) | `.py` | A2 acceptance: every migrated v2 guard decides exactly as the v1 table |
| [`test_persistent_approval_portal_contract.py`](test_persistent_approval_portal_contract.py) | `.py` | Implementa `PersistentApprovalPortalContractTests`. |
| [`test_persistent_human_approval_policy.py`](test_persistent_human_approval_policy.py) | `.py` | Implementa `load_api`, `PersistentHumanApprovalPolicyTests`. |
| [`test_personal_repo_survives_initial_publish.py`](test_personal_repo_survives_initial_publish.py) | `.py` | Implementa `PersonalRepoSurvivesInitialPublishTests`. |
| [`test_platform_backup_progress_modal.py`](test_platform_backup_progress_modal.py) | `.py` | Implementa `PlatformBackupProgressModalTests`. |
| [`test_platform_guide_canonical.py`](test_platform_guide_canonical.py) | `.py` | Implementa `CanonicalPlatformGuideTests`. |
| [`test_platform_guide_github.py`](test_platform_guide_github.py) | `.py` | Implementa `PlatformGuideGithubTests`. |
| [`test_portal_approval_redirect_v2.py`](test_portal_approval_redirect_v2.py) | `.py` | Implementa `PortalApprovalRedirectV2Tests`. |
| [`test_portal_artifact_upload_bridge.py`](test_portal_artifact_upload_bridge.py) | `.py` | Implementa `Response`, `Handler`, `PortalArtifactUploadBridgeTests`. |
| [`test_portal_artifact_upload_routes.py`](test_portal_artifact_upload_routes.py) | `.py` | Implementa `PortalArtifactUploadRoutesTests`. |
| [`test_portal_launcher_base_compatibility.py`](test_portal_launcher_base_compatibility.py) | `.py` | Implementa `PortalLauncherBaseCompatibilityTests`. |
| [`test_portal_no_legacy_visual_fallback.py`](test_portal_no_legacy_visual_fallback.py) | `.py` | Implementa `PortalNoLegacyVisualFallbackTests`. |
| [`test_portal_sqlite_wal_resilience.py`](test_portal_sqlite_wal_resilience.py) | `.py` | Implementa `load_delete_module`, `PortalSQLiteWalResilienceTests`. |
| [`test_project_acl_visual_layout.py`](test_project_acl_visual_layout.py) | `.py` | Implementa `ProjectAclVisualLayoutTests`. |
| [`test_project_backup_download_public_route.py`](test_project_backup_download_public_route.py) | `.py` | Implementa `ProjectBackupDownloadPublicRouteTests`. |
| [`test_project_capabilities_catalog_parser.py`](test_project_capabilities_catalog_parser.py) | `.py` | Implementa `ProjectCapabilitiesCatalogParserTests`. |
| [`test_project_centered_navigation.py`](test_project_centered_navigation.py) | `.py` | Implementa `ProjectCenteredNavigationTest`. |
| [`test_project_config_active_reconciliation.py`](test_project_config_active_reconciliation.py) | `.py` | Implementa `ActiveProjectConfigurationReconciliationTests`. |
| [`test_project_config_controller_http.py`](test_project_config_controller_http.py) | `.py` | Implementa `ProjectConfigControllerHTTPTests`. |
| [`test_project_config_reconciler_behavior.py`](test_project_config_reconciler_behavior.py) | `.py` | Implementa `ProjectConfigReconcilerBehaviorTests`. |
| [`test_project_creation_modal_runtime.py`](test_project_creation_modal_runtime.py) | `.py` | Implementa `ProjectCreationModalRuntimeTest`. |
| [`test_project_creation_wizard_steps.py`](test_project_creation_wizard_steps.py) | `.py` | Implementa `ProjectCreationWizardStepsTest`. |
| [`test_project_delete_already_deleted_ui.py`](test_project_delete_already_deleted_ui.py) | `.py` | Implementa `ProjectDeleteAlreadyDeletedUITests`. |
| [`test_project_delete_cleans_derived_komodo_resources.py`](test_project_delete_cleans_derived_komodo_resources.py) | `.py` | Implementa `ProjectDeleteCleansDerivedKomodoResourcesTests`. |
| [`test_project_delete_confirmation_normalization.py`](test_project_delete_confirmation_normalization.py) | `.py` | Implementa `ProjectDeleteConfirmationNormalizationTests`. |
| [`test_project_delete_global_groups_and_polling.py`](test_project_delete_global_groups_and_polling.py) | `.py` | Implementa `ProjectDeleteGlobalGroupsAndPollingTests`. |
| [`test_project_delete_idempotent_cleanup.py`](test_project_delete_idempotent_cleanup.py) | `.py` | Implementa `ProjectDeleteIdempotentCleanupTests`. |
| [`test_project_delete_personal_forgejo_repo.py`](test_project_delete_personal_forgejo_repo.py) | `.py` | Implementa `ProjectDeletePersonalForgejoRepoTests`. |
| [`test_project_delete_tracking_modal.py`](test_project_delete_tracking_modal.py) | `.py` | Implementa `ProjectDeleteTrackingModalTests`. |
| [`test_project_delete_wizard_required.py`](test_project_delete_wizard_required.py) | `.py` | Implementa `ProjectDeleteWizardRequiredTests`. |
| [`test_project_environment_controller.py`](test_project_environment_controller.py) | `.py` | Implementa `load_module`, `ProjectEnvironmentControllerTests`. |
| [`test_project_environment_dotenv_contract.py`](test_project_environment_dotenv_contract.py) | `.py` | Implementa `load_module`, `ProjectEnvironmentDotenvContractTests`. |
| [`test_project_environment_effective_resolution.py`](test_project_environment_effective_resolution.py) | `.py` | Implementa `ProjectEnvironmentEffectiveResolutionTests`. |
| [`test_project_environment_mcp_contract.py`](test_project_environment_mcp_contract.py) | `.py` | Implementa `load_gateway`, `ProjectEnvironmentMCPContractTests`. |
| [`test_project_environment_secret_store.py`](test_project_environment_secret_store.py) | `.py` | Implementa `load_secret`, `ProjectEnvironmentSecretStoreTests`. |
| [`test_project_environment_web_api.py`](test_project_environment_web_api.py) | `.py` | Implementa `load_module`, `ProjectEnvironmentWebAPITests`. |
| [`test_project_environments_overview.py`](test_project_environments_overview.py) | `.py` | Implementa `load_module`, `ProjectEnvironmentsOverviewTests`. |
| [`test_project_manifest_controller.py`](test_project_manifest_controller.py) | `.py` | Implementa `ProjectManifestControllerTests`. |
| [`test_project_manifest_environment_toolchain_v1.py`](test_project_manifest_environment_toolchain_v1.py) | `.py` | Implementa `load_module`, `ProjectManifestEnvironmentToolchainV1Tests`. |
| [`test_project_observability_mcp_web.py`](test_project_observability_mcp_web.py) | `.py` | Implementa `load_web`, `load_gateway`, `ProjectObservabilityMCPWebTests`. |
| [`test_project_observability_service.py`](test_project_observability_service.py) | `.py` | Implementa `load_module`, `ProjectObservabilityServiceTests`. |
| [`test_project_owner_delete_authorization.py`](test_project_owner_delete_authorization.py) | `.py` | Implementa `load_module`, `ProjectOwnerDeleteAuthorizationTests`, `ProjectOwnerDeleteRouteContractTests`. |
| [`test_project_provision_resume_contract.py`](test_project_provision_resume_contract.py) | `.py` | Implementa `ProjectProvisionResumeContractTests`. |
| [`test_project_provision_status_recovery.py`](test_project_provision_status_recovery.py) | `.py` | Implementa `load_module`, `ProjectProvisionStatusRecoveryTests`. |
| [`test_project_provisioning_contract.py`](test_project_provisioning_contract.py) | `.py` | Implementa `ProjectProvisioningContractTest`. |
| [`test_project_provisioning_live_wizard.py`](test_project_provisioning_live_wizard.py) | `.py` | Implementa `ProjectProvisioningLiveWizardTests`. |
| [`test_project_publication_configuration_v1.py`](test_project_publication_configuration_v1.py) | `.py` | Implementa `load`, `ProjectPublicationConfigurationV1Tests`. |
| [`test_project_repo_oauth_owner.py`](test_project_repo_oauth_owner.py) | `.py` | Implementa `ProjectRepoOauthOwnerTests`. |
| [`test_project_repository_manual.py`](test_project_repository_manual.py) | `.py` | Implementa `ProjectRepositoryManualTests`. |
| [`test_project_resource_reorganization.py`](test_project_resource_reorganization.py) | `.py` | Implementa `ProjectResourceReorganizationTest`, `ActiveProjectRendererContractTest`, `DefinitiveProjectManagementRendererTest`. |
| [`test_project_runtime_reconciler_mcp_web.py`](test_project_runtime_reconciler_mcp_web.py) | `.py` | Implementa `load_web`, `load_gateway`, `ProjectRuntimeReconcilerMCPWebTests`. |
| [`test_project_runtime_reconciler_states.py`](test_project_runtime_reconciler_states.py) | `.py` | Implementa `load_module`, `ProjectRuntimeReconcilerStateTests`. |
| [`test_project_runtime_status_ui.py`](test_project_runtime_status_ui.py) | `.py` | Implementa `ProjectRuntimeStatusUITests`. |
| [`test_project_secret_controller_contract.py`](test_project_secret_controller_contract.py) | `.py` | Implementa `ProjectSecretControllerContractTests`. |
| [`test_project_secret_mcp_contract.py`](test_project_secret_mcp_contract.py) | `.py` | Implementa `load_gateway`, `ProjectSecretMCPContractTests`. |
| [`test_project_secret_web_api.py`](test_project_secret_web_api.py) | `.py` | Implementa `load_module`, `ProjectSecretWebAPITests`. |
| [`test_project_terminal_dedicated_flow.py`](test_project_terminal_dedicated_flow.py) | `.py` | Implementa `ProjectTerminalDedicatedFlowTests`. |
| [`test_project_toolchain_web_api.py`](test_project_toolchain_web_api.py) | `.py` | Implementa `load_module`, `ProjectToolchainWebAPITests`. |
| [`test_provision_worker_persists_forgejo_owner.py`](test_provision_worker_persists_forgejo_owner.py) | `.py` | Implementa `ProvisionWorkerPersistsForgejoOwnerTests`. |
| [`test_provision_worker_systemd_recovery.py`](test_provision_worker_systemd_recovery.py) | `.py` | Implementa `ProvisionWorkerSystemdRecoveryTest`. |
| [`test_provisioning_metadata_persistence_contract.py`](test_provisioning_metadata_persistence_contract.py) | `.py` | Implementa `ProvisioningMetadataPersistenceContractTest`. |
| [`test_provisioning_policy_readme_dark_theme.py`](test_provisioning_policy_readme_dark_theme.py) | `.py` | Implementa `ProvisioningPolicyReadmeDarkThemeTest`. |
| [`test_provisioning_runtime_completion_contract.py`](test_provisioning_runtime_completion_contract.py) | `.py` | Implementa `ProvisioningRuntimeCompletionContractTest`. |
| [`test_provisioning_waits_start_page_theme.py`](test_provisioning_waits_start_page_theme.py) | `.py` | Implementa `ProvisioningWaitsStartPageThemeTest`. |
| [`test_publication_deploy_promotion_race.py`](test_publication_deploy_promotion_race.py) | `.py` | Implementa `PublicationDeployPromotionRaceTests`. |
| [`test_publication_jobs.py`](test_publication_jobs.py) | `.py` | Implementa `PublicationJobsTest`. |
| [`test_publication_management_ui.py`](test_publication_management_ui.py) | `.py` | Implementa `PublicationManagementUITest`. |
| [`test_publication_personal_owner_base_project.py`](test_publication_personal_owner_base_project.py) | `.py` | Implementa `PublicationPersonalOwnerBaseProjectTests`. |
| [`test_publication_runtime_fallback.py`](test_publication_runtime_fallback.py) | `.py` | Implementa `PublicationRuntimeFallbackTest`. |
| [`test_publication_runtime_links_and_actions.py`](test_publication_runtime_links_and_actions.py) | `.py` | Implementa `PublicationRuntimeLinksAndActionsTests`. |
| [`test_recreate_owner_and_initial_terminal.py`](test_recreate_owner_and_initial_terminal.py) | `.py` | Implementa `RecreateOwnerAndInitialTerminalTests`. |
| [`test_registry.py`](test_registry.py) | `.py` | Implementa `_identity`, `_req`, `RegistryTest`. |
| [`test_release_flow_wizard_ui.py`](test_release_flow_wizard_ui.py) | `.py` | Implementa `ReleaseFlowWizardUITests`. |
| [`test_repository_readme_landing.py`](test_repository_readme_landing.py) | `.py` | Implementa `test_repository_uses_root_readme_as_github_landing_page`, `test_readme_visual_assets_exist_and_svg_is_valid`, `test_documentation_generator_does_not_recreate_shadow_readme`. |
| [`test_router_warmup_visual.py`](test_router_warmup_visual.py) | `.py` | Implementa `RouterWarmupVisualTests`. |
| [`test_runtime_cards_open_komodo.py`](test_runtime_cards_open_komodo.py) | `.py` | Implementa `RuntimeCardsOpenKomodoTests`. |
| [`test_runtime_completion_contract.py`](test_runtime_completion_contract.py) | `.py` | Implementa `RuntimeCompletionContractTest`. |
| [`test_runtime_diagnostics_new_tab.py`](test_runtime_diagnostics_new_tab.py) | `.py` | Implementa `RuntimeDiagnosticsNewTabTests`. |
| [`test_runtime_framework_inspection.py`](test_runtime_framework_inspection.py) | `.py` | Implementa `RuntimeFrameworkInspectionContractTest`. |
| [`test_runtime_info_active_publication.py`](test_runtime_info_active_publication.py) | `.py` | Implementa `RuntimeInfoActivePublicationTests`. |
| [`test_runtime_info_reconcile_retry.py`](test_runtime_info_reconcile_retry.py) | `.py` | Implementa `RuntimeInfoReconcileRetryTests`. |
| [`test_runtime_modal_body_layer.py`](test_runtime_modal_body_layer.py) | `.py` | Implementa `RuntimeModalBodyLayerTests`. |
| [`test_runtime_modal_web.py`](test_runtime_modal_web.py) | `.py` | Implementa `RuntimeModalWebTests`. |
| [`test_shared_user_related_stacks.py`](test_shared_user_related_stacks.py) | `.py` | Implementa `SharedUserRelatedStacksTests`. |
| [`test_shell_and_services.py`](test_shell_and_services.py) | `.py` | Shell rendering and per-module service unit tests (A5). |
| [`test_supabase_mcp_database_connector_contract.py`](test_supabase_mcp_database_connector_contract.py) | `.py` | Implementa `SupabaseMCPDatabaseConnectorContractTest`. |
| [`test_supabase_mcp_sql_policy.py`](test_supabase_mcp_sql_policy.py) | `.py` | Implementa `SupabaseMCPSQLPolicyTest`. |
| [`test_template_fileops_personal_owner.py`](test_template_fileops_personal_owner.py) | `.py` | Implementa `TemplateFileOpsPersonalOwnerTests`. |
| [`test_tenant_always_on_final_handler.py`](test_tenant_always_on_final_handler.py) | `.py` | Implementa `TenantAlwaysOnFinalHandlerTests`. |
| [`test_tenant_auto_off_and_countdown.py`](test_tenant_auto_off_and_countdown.py) | `.py` | Implementa `TenantAutoOffCountdownTests`. |
| [`test_tenant_backup_dynamic_and_graceful_tls.py`](test_tenant_backup_dynamic_and_graceful_tls.py) | `.py` | Implementa `TenantBackupAndTlsTests`. |
| [`test_tenant_delete_job_receipt.py`](test_tenant_delete_job_receipt.py) | `.py` | Implementa `TenantDeleteJobReceiptTests`. |
| [`test_tenant_guard_auto_recovery.py`](test_tenant_guard_auto_recovery.py) | `.py` | Implementa `load_module`, `TenantGuardAutoRecoveryTests`. |
| [`test_tenant_https_entry_contract.py`](test_tenant_https_entry_contract.py) | `.py` | Implementa `TenantHttpsEntryContractTest`. |
| [`test_tenant_port_allocator_contract.py`](test_tenant_port_allocator_contract.py) | `.py` | Implementa `TenantPortAllocatorContractTests`. |
| [`test_tenant_proxy_lifecycle_contract.py`](test_tenant_proxy_lifecycle_contract.py) | `.py` | Implementa `TenantProxyLifecycleContractTest`. |
| [`test_terminal_and_publication_layout.py`](test_terminal_and_publication_layout.py) | `.py` | Implementa `TerminalAndPublicationLayoutTests`. |
| [`test_terminal_reconciles_unified_stack.py`](test_terminal_reconciles_unified_stack.py) | `.py` | Implementa `TerminalReconcilesUnifiedStackTests`. |
| [`test_terminal_stack_resolution_contract.py`](test_terminal_stack_resolution_contract.py) | `.py` | Implementa `TerminalStackResolutionContractTest`. |
| [`test_terminal_uses_active_publication_stack.py`](test_terminal_uses_active_publication_stack.py) | `.py` | Implementa `TerminalUsesActivePublicationStackTests`. |
| [`test_terminal_uses_authenticated_actor.py`](test_terminal_uses_authenticated_actor.py) | `.py` | Implementa `TerminalUsesAuthenticatedActorTests`. |
| [`test_toolchain_catalog_policy.py`](test_toolchain_catalog_policy.py) | `.py` | Implementa `load`, `ToolchainCatalogPolicyTests`. |
| [`test_toolchain_lifecycle_broker.py`](test_toolchain_lifecycle_broker.py) | `.py` | Implementa `load_broker`, `ToolchainLifecycleBrokerTests`, `hashlib_sha`. |
| [`test_toolchain_mcp_contract.py`](test_toolchain_mcp_contract.py) | `.py` | Implementa `load_gateway`, `ToolchainMCPContractTests`. |
| [`test_ui_security_gate_contract.py`](test_ui_security_gate_contract.py) | `.py` | Implementa `UISecurityGateContractTests`. |
| [`test_unified_project_runtime.py`](test_unified_project_runtime.py) | `.py` | Implementa `UnifiedProjectRuntimeTests`. |
| [`test_unified_runtime_documentation.py`](test_unified_runtime_documentation.py) | `.py` | Implementa `UnifiedRuntimeDocumentationTests`. |
| [`test_user_owned_forgejo_and_komodo_acl.py`](test_user_owned_forgejo_and_komodo_acl.py) | `.py` | Implementa `UserOwnedForgejoAndKomodoAclTests`. |
| [`test_versioned_unified_runtime_publication.py`](test_versioned_unified_runtime_publication.py) | `.py` | Implementa `VersionedUnifiedRuntimePublicationTests`. |
| [`test_w_h_p_release_flow.py`](test_w_h_p_release_flow.py) | `.py` | Implementa `WHPReleaseFlowTests`. |
| [`test_workspace_artifact_direct_http.py`](test_workspace_artifact_direct_http.py) | `.py` | Implementa `WorkspaceArtifactDirectHTTPTests`. |
| [`test_workspace_artifact_direct_upload.py`](test_workspace_artifact_direct_upload.py) | `.py` | Implementa `WorkspaceArtifactDirectUploadTests`. |
| [`test_workspace_artifact_session_import.py`](test_workspace_artifact_session_import.py) | `.py` | Implementa `WorkspaceArtifactSessionImportTests`. |
| [`test_workspace_artifact_upload.py`](test_workspace_artifact_upload.py) | `.py` | Implementa `WorkspaceArtifactUploadTests`. |
| [`test_workspace_change_set.py`](test_workspace_change_set.py) | `.py` | Implementa `b64`, `WorkspaceChangeSetTests`. |

> Esta seção é gerada por `scripts/generate-directory-readmes.py`. Conteúdo manual fora dos marcadores é preservado.

<!-- CLOUDIFF-AUTO-DOC:END -->
