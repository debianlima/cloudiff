# Manutenção pelo GitHub

## Fluxo recomendado

1. Crie uma branch a partir de `main`.
2. Edite o componente na pasta correspondente.
3. Execute `scripts/validate.sh`.
4. Abra um pull request e aguarde o workflow `Validate CloudIFF source`.
5. Faça a promoção para os hosts por uma release controlada, nunca copiando diretamente para produção.

## Mapeamento

| Repositório | Destino |
|---|---|
| `components/control-plane/current-apps/<serviço>` | release imutável em `/srv/cloudif/app-releases/<serviço>` no control plane |
| `components/control-plane/srv/cloudif/lib` | `/srv/cloudif/lib` |
| `components/control-plane/srv/cloudif/bin` | `/srv/cloudif/bin` |
| `components/*/usr/local/sbin` | `/usr/local/sbin` do nó correspondente |
| `components/*/etc/systemd/system` | `/etc/systemd/system` do nó correspondente |
| `components/runtime/etc/komodo/stacks` | `/etc/komodo/stacks` no runtime |
| `components/proxy/srv/cloudif/proxy` | `/srv/cloudif/proxy` no proxy |
| `tenant-templates/srv/cloudif/tenants` | templates sanitizados em `/srv/cloudif/tenants` |

## Monitoramento

Código principal:

- `components/control-plane/current-apps/monitor-current/`
- `components/control-plane/usr/local/sbin/cloudif-healthcheck.sh`
- `components/*/usr/local/sbin/cloudif-node-metrics.py`
- units `cloudif-monitor-*`, `cloudif-healthcheck-*` e `cloudif-node-metrics.*`

## Agentes

Código principal:

- `components/control-plane/current-apps/agent-controller-current/`
- `components/control-plane/current-apps/agent-registry-current/`
- `components/runtime/current-apps/forja-agent-current/`
- `components/runtime/current-apps/komodo-agent-current/`
- `components/proxy/current-apps/publisher-agent-current/`

## Configuração

Use os modelos em `config/`. Valores reais devem permanecer no cofre ou nos arquivos protegidos dos hosts.
