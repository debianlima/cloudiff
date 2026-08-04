# CloudIFF

Repositório consolidado da plataforma CloudIFF.

## Documentação técnica

Este repositório funciona também como uma apostila técnica da plataforma:

- [Manual técnico completo](docs/manual-tecnico/README.md)
- [Arquitetura e diagramas](docs/manual-tecnico/01-ARQUITETURA.md)
- [Runtime unificado de projetos](docs/manual-tecnico/11-RUNTIME-UNIFICADO.md)
- [Fluxos de processo](docs/manual-tecnico/02-FLUXOS.md)
- [Agentes e funções](docs/manual-tecnico/03-AGENTES.md)
- [Protocolos de reconciliação](docs/manual-tecnico/04-RECONCILIACAO.md)
- [Modelo e dicionário de dados](docs/manual-tecnico/05-DADOS.md)
- [Mensagens, aprovações e segurança](docs/manual-tecnico/06-MENSAGENS-E-APROVACOES.md)
- [Catálogo de agentes](docs/CATALOGO-DE-AGENTES.md)
- [Catálogo de serviços](docs/CATALOGO-DE-SERVICOS.md)
- [Catálogo de rotas](docs/CATALOGO-DE-ROTAS.md)
- [Inventário de todos os arquivos](docs/INVENTARIO-DE-ARQUIVOS.md)


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

<!-- CLOUDIFF-AUTO-DOC:BEGIN -->

## Inventário automático de `.`

Diretório versionado da CloudIFF.

| Item | Tipo | Finalidade |
|---|---|---|
| [`.github/`](.github/) | Diretório | Automação e integração contínua do GitHub. |
| [`components/`](components/) | Diretório | Diretório versionado da CloudIFF. |
| [`config/`](config/) | Diretório | Configurações por nó e contratos declarativos. |
| [`docs/`](docs/) | Diretório | Documentação técnica, inventários e evidências. |
| [`portal/`](portal/) | Diretório | Arquitetura modular, interface, configuração e testes do Portal. |
| [`scripts/`](scripts/) | Diretório | Ferramentas de validação, documentação e manutenção do repositório. |
| [`tenant-templates/`](tenant-templates/) | Diretório | Modelos e snapshots de tenants Supabase. |
| [`.gitignore`](.gitignore) | `arquivo` | Arquivo de suporte da plataforma. |
| [`SECURITY.md`](SECURITY.md) | `.md` | Documento técnico ou operacional. |

> Esta seção é gerada por `scripts/generate-directory-readmes.py`. Conteúdo manual fora dos marcadores é preservado.

<!-- CLOUDIFF-AUTO-DOC:END -->
