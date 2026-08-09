# Sbin

Componentes implantados no host de runtime, Forgejo, Komodo e executores.

<!-- CLOUDIFF-AUTO-DOC:BEGIN -->

## Inventário automático de `components/runtime/usr/local/sbin`

Componentes implantados no host de runtime, Forgejo, Komodo e executores.

| Item | Tipo | Finalidade |
|---|---|---|
| [`cloudif-configure-komodo-embed-auth.sh`](cloudif-configure-komodo-embed-auth.sh) | `.sh` | Automação Shell operacional da plataforma. |
| [`cloudif-forja-agent.py`](cloudif-forja-agent.py) | `.py` | Implementa `read_env`, `now`, `clean_url`, `bool_value`, `jdump`, `json_response` e outros componentes. |
| [`cloudif-komodo-agent.py`](cloudif-komodo-agent.py) | `.py` | Implementa `now`, `init_db`, `db_exec`, `db_query`, `record_deployment`, `load_env` e outros componentes. |
| [`cloudif-komodo-api-call.py`](cloudif-komodo-api-call.py) | `.py` | Implementa `load_env`, `headers`, `call`. |
| [`cloudif-komodo-authz-sync.py`](cloudif-komodo-authz-sync.py) | `.py` | Implementa `run`. |
| [`cloudif-komodo-project-authz.py`](cloudif-komodo-project-authz.py) | `.py` | Implementa `main`. |
| [`cloudif-machine-certificate-renew.py`](cloudif-machine-certificate-renew.py) | `.py` | Implementa `load_env`, `run`, `serial`, `cert_expiring`, `opener`, `post` e outros componentes. |
| [`cloudif-machine-executor.py`](cloudif-machine-executor.py) | `.py` | Módulo Python da plataforma. |
| [`cloudif-machine-guardian.py`](cloudif-machine-guardian.py) | `.py` | Implementa `send`, `main`. |
| [`cloudif-machine-harvester.py`](cloudif-machine-harvester.py) | `.py` | Implementa `verify_policy_envelope`, `controller_open`, `run`, `ensure_identity`, `cert_state`, `cert_record` e outros componentes. |
| [`cloudif-mongosh-komodo`](cloudif-mongosh-komodo) | `arquivo` | Arquivo de suporte da plataforma. |
| [`cloudif-node-metrics.py`](cloudif-node-metrics.py) | `.py` | Implementa `run`, `network_summary`, `docker_summary`, `metrics`, `H`. |
| [`cloudif-release-maintenance`](cloudif-release-maintenance) | `arquivo` | Arquivo de suporte da plataforma. |

> Esta seção é gerada por `scripts/generate-directory-readmes.py`. Conteúdo manual fora dos marcadores é preservado.

<!-- CLOUDIFF-AUTO-DOC:END -->
