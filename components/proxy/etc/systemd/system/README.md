# System

Componentes implantados no host de proxy e publicação.

<!-- CLOUDIFF-AUTO-DOC:BEGIN -->

## Inventário automático de `components/proxy/etc/systemd/system`

Componentes implantados no host de proxy e publicação.

| Item | Tipo | Finalidade |
|---|---|---|
| [`cloudif-access-push.service.d/`](cloudif-access-push.service.d/) | Diretório | Componentes implantados no host de proxy e publicação. |
| [`cloudif-access-api.service`](cloudif-access-api.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-access-collector.service`](cloudif-access-collector.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-access-collector.timer`](cloudif-access-collector.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-access-push.service`](cloudif-access-push.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-access-push.timer`](cloudif-access-push.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-admin-cert-renew.service`](cloudif-admin-cert-renew.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-admin-cert-renew.timer`](cloudif-admin-cert-renew.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-machine-certificate-renew.service`](cloudif-machine-certificate-renew.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-machine-certificate-renew.timer`](cloudif-machine-certificate-renew.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-machine-guardian.service`](cloudif-machine-guardian.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-machine-guardian.timer`](cloudif-machine-guardian.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-machine-harvester.service`](cloudif-machine-harvester.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-machine-harvester.timer`](cloudif-machine-harvester.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-node-metrics.service`](cloudif-node-metrics.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-npm-backup.service`](cloudif-npm-backup.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-npm-backup.timer`](cloudif-npm-backup.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-npm-healthcheck.service`](cloudif-npm-healthcheck.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-npm-healthcheck.timer`](cloudif-npm-healthcheck.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |
| [`cloudif-npm-publisher-agent.service`](cloudif-npm-publisher-agent.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-publication-cert-renew.service`](cloudif-publication-cert-renew.service) | `.service` | Unidade systemd que inicia e protege um serviço CloudIFF. |
| [`cloudif-publication-cert-renew.timer`](cloudif-publication-cert-renew.timer) | `.timer` | Timer systemd que agenda a unidade correspondente. |

> Esta seção é gerada por `scripts/generate-directory-readmes.py`. Conteúdo manual fora dos marcadores é preservado.

<!-- CLOUDIFF-AUTO-DOC:END -->
