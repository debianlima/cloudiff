# Sbin

Componentes implantados no host de proxy e publicação.

<!-- CLOUDIFF-AUTO-DOC:BEGIN -->

## Inventário automático de `components/proxy/usr/local/sbin`

Componentes implantados no host de proxy e publicação.

| Item | Tipo | Finalidade |
|---|---|---|
| [`cloudif-machine-certificate-renew.py`](cloudif-machine-certificate-renew.py) | `.py` | Implementa `load_env`, `run`, `serial`, `cert_expiring`, `opener`, `post` e outros componentes. |
| [`cloudif-machine-executor.py`](cloudif-machine-executor.py) | `.py` | Módulo Python da plataforma. |
| [`cloudif-machine-guardian.py`](cloudif-machine-guardian.py) | `.py` | Implementa `send`, `main`. |
| [`cloudif-machine-harvester.py`](cloudif-machine-harvester.py) | `.py` | Implementa `verify_policy_envelope`, `controller_open`, `run`, `ensure_identity`, `cert_state`, `cert_record` e outros componentes. |
| [`cloudif-node-metrics.py`](cloudif-node-metrics.py) | `.py` | Implementa `run`, `network_summary`, `docker_summary`, `metrics`, `H`. |
| [`cloudif-npm-backup.sh`](cloudif-npm-backup.sh) | `.sh` | Script Shell de backup, retenção ou sincronização. |
| [`cloudif-npm-healthcheck.sh`](cloudif-npm-healthcheck.sh) | `.sh` | Automação Shell operacional da plataforma. |
| [`cloudif-npm-publisher-agent.py`](cloudif-npm-publisher-agent.py) | `.py` | Implementa `env`, `load_state`, `save_state`, `run`, `cert_exists`, `cert_covers` e outros componentes. |
| [`cloudif-publication-cert-renew.sh`](cloudif-publication-cert-renew.sh) | `.sh` | Automação Shell operacional da plataforma. |
| [`cloudif-release-maintenance`](cloudif-release-maintenance) | `arquivo` | Arquivo de suporte da plataforma. |

> Esta seção é gerada por `scripts/generate-directory-readmes.py`. Conteúdo manual fora dos marcadores é preservado.

<!-- CLOUDIFF-AUTO-DOC:END -->
