# CloudIFF

Repositório consolidado da plataforma CloudIFF.

Este snapshot reúne o código-fonte e as configurações versionáveis dos três nós da plataforma:

- **control-plane**: Portal, MCP, AuthZ, tenant guard, reconciliadores, monitores e testes;
- **runtime**: Komodo, agentes, stacks e serviços de execução;
- **proxy**: Nginx Proxy Manager, configurações customizadas e automações de proxy;
- **tenant-templates**: templates, scripts, testes e composições dos tenants Supabase.

## Estrutura

```text
components/
  control-plane/
    current-apps/       Releases atuais dos serviços
    srv/cloudif/lib/    Bibliotecas compartilhadas
    srv/cloudif/tests/  Testes e gates
    srv/cloudif/router/ Configuração do roteador
    usr/local/sbin/     Automação operacional
    etc/systemd/system/ Unidades e timers
  runtime/
    current-apps/       Releases atuais do runtime
    etc/komodo/stacks/  Stacks versionáveis
    usr/local/sbin/     Agentes e automações
    etc/systemd/system/ Unidades e timers
  proxy/
    current-apps/       Releases atuais do proxy
    srv/cloudif/proxy/  Configuração customizada do Nginx
    usr/local/sbin/     Automações
    etc/systemd/system/ Unidades e timers
tenant-templates/
  srv/cloudif/tenants/  Templates sanitizados dos tenants
```

## Segurança

Este repositório não contém:

- senhas, tokens ou chaves privadas;
- arquivos `.env`;
- certificados;
- bancos SQLite/PostgreSQL;
- logs;
- backups;
- volumes e dados de runtime;
- snapshots publicados.

Valores sensíveis devem ser injetados por variáveis de ambiente ou pelo gerenciador de segredos da infraestrutura.

## Origem do snapshot

O código foi exportado dos nós ativos da plataforma e sanitizado antes do commit inicial. Os diretórios `current-apps` representam somente os releases efetivos apontados pelos links de produção no momento da exportação.

## Licença e uso

Uso institucional. Antes de publicar este repositório como público, revise políticas internas, dependências de terceiros e informações de arquitetura.

## Validação e manutenção

Antes de enviar alterações:

```bash
scripts/validate.sh
```

Consulte:

- `docs/MAINTENANCE.md` para o fluxo de edição e promoção;
- `docs/REPOSITORY_AUDIT.md` para a auditoria de cobertura;
- `docs/COVERAGE_AUDIT.json` para a comparação com os hosts ativos;
- `docs/INVENTORY.json` para o inventário de arquivos.

## Portal v2

A migração incremental do Portal está em `portal/`. Consulte:

- `docs/portal-v2/PLANO-DE-APERFEICOAMENTO.md`;
- `docs/portal-v2/GUIA-DE-MIGRACAO.md`;
- `docs/portal-v2/prototipo.html`.

As Fases 0 e 1 estão implementadas em coexistência. O Portal legado permanece o
fallback de produção até a migração individual das rotas.
