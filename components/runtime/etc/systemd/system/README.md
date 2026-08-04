# System

Componentes implantados no host de runtime, Forgejo, Komodo e executores.

<!-- CLOUDIFF-AUTO-DOC:BEGIN -->

## Inventário automático de `components/runtime/etc/systemd/system`

Componentes implantados no host de runtime, Forgejo, Komodo e executores.

| Item | Tipo | Finalidade |
|---|---|---|
| [`cloudif-forja-agent.service.d/`](cloudif-forja-agent.service.d/) | Diretório | Componentes implantados no host de runtime, Forgejo, Komodo e executores. |
| [`cloudif-production-sealed-target.service.d/`](cloudif-production-sealed-target.service.d/) | Diretório | Componentes implantados no host de runtime, Forgejo, Komodo e executores. |
| [`cloudif-artifact-executor.service`](cloudif-artifact-executor.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-forja-agent.service`](cloudif-forja-agent.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-komodo-agent.service`](cloudif-komodo-agent.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-komodo-authz-sync.service`](cloudif-komodo-authz-sync.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-komodo-authz-sync.timer`](cloudif-komodo-authz-sync.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-machine-certificate-renew.service`](cloudif-machine-certificate-renew.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-machine-certificate-renew.timer`](cloudif-machine-certificate-renew.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-machine-guardian.service`](cloudif-machine-guardian.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-machine-guardian.timer`](cloudif-machine-guardian.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-machine-harvester.service`](cloudif-machine-harvester.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-machine-harvester.timer`](cloudif-machine-harvester.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-node-metrics.service`](cloudif-node-metrics.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-node24-pipeline.service`](cloudif-node24-pipeline.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-node24-pipeline.timer`](cloudif-node24-pipeline.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-preview-executor.service`](cloudif-preview-executor.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-production-canary-executor.service`](cloudif-production-canary-executor.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-production-homologation-executor.service`](cloudif-production-homologation-executor.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-production-public-executor.service`](cloudif-production-public-executor.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-production-sealed-target.service`](cloudif-production-sealed-target.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |

> Esta seção é gerada por `scripts/generate-directory-readmes.py`. Conteúdo manual fora dos marcadores é preservado.

<!-- CLOUDIFF-AUTO-DOC:END -->
