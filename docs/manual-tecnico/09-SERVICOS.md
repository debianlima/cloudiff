# Catálogo de serviços

Os arquivos `.service` e `.timer` em `components/*/etc/systemd/system` são a fonte de implantação. O catálogo completo e atualizado é gerado nos READMEs desses diretórios.

## Grupos

| Grupo | Exemplos |
|---|---|
| Interface | Portal, dashboard e painéis. |
| Identidade e autorização | Agent Registry, Authz Gate, Approval API e onboarding. |
| Execução | Build Worker, Artifact Executor, Preview Executor e executores de produção. |
| Entrega | Deployment Broker, Publication Worker, NPM Publisher e certificados. |
| Estado | Reconcile Worker, Transaction Reconciler, Project State Reconcile. |
| Banco | Supabase brokers, tenant guard, backup e sessão. |
| Observabilidade | Monitor API, collector, audit, notifications e smoke tests. |
| Manutenção | Retention, storage guard, backups, restore tests e integrity timers. |
