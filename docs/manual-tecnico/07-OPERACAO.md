# Operação, falhas e recuperação

## Jobs duráveis

Provisionamento e exclusão são jobs persistentes. A interface consulta JSON de estado; reinícios ou recargas do roteador são tratados como reconexão, não como falha automática.

## Backups

- backup de aplicação por projeto;
- backup lógico final antes da exclusão de tenant;
- arquivo de configuração do tenant;
- backup de configuração da plataforma;
- sincronização opcional com servidor remoto;
- retenção configurável e histórico somente leitura.

## Diagnóstico por etapa

| Sintoma | Verificação |
|---|---|
| Forgejo falhou | Relatório do componente, API do Forja Agent e existência do repositório. |
| Komodo falhou | Projeto/stack, repositório local, build e containers. |
| Tenant incompleto | Registry, `docker-compose.yml`, 11 serviços e health básico. |
| Publicação 502 | Alias da rede, porta do container, healthcheck, gateway e proxy. |
| Modal recebeu HTML | Usar endpoint JSON dedicado e reconectar em 404/502/503/504. |
| Exclusão aparece falha a 100% | Consultar recibo durável e `result.json`. |

## Recuperação segura

1. Não repetir imediatamente uma ação destrutiva.
2. Ler job, recibo e relatório.
3. Confirmar recursos reais.
4. Retomar o mesmo job sob o lock do recurso.
5. Usar operações `ensure`, `repair`, `deploy-full` e reconciliação.
6. Só remover manualmente resíduos depois de preservar evidências e backup.
