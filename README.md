# CloudIFF

Plataforma institucional para criar, publicar e administrar projetos web isolados, com repositório Git, runtime, banco Supabase, agentes MCP, permissões e observabilidade em um único portal.

![Visão geral do Portal CloudIFF](docs/assets/cloudiff-interface.jpg)

> Visão representativa da interface versionada no repositório. O acesso ao ambiente real exige autenticação institucional.

## Para que serve

A CloudIFF transforma o provisionamento de um projeto em um fluxo único e auditável. Cada projeto pode receber:

- repositório privado no Forgejo, com clone HTTPS e SSH;
- container isolado com Apache, PHP e Node.js;
- tenant Supabase com Postgres, Auth, Storage, Realtime e APIs;
- publicação e rollback operados pelo Komodo;
- identidade MCP própria para agentes de IA;
- ACL por projeto, aprovações humanas, backups e monitoramento.

A plataforma atende estudantes, professores e administradores que precisam desenvolver, revisar e publicar aplicações sem compartilhar credenciais ou misturar recursos entre projetos.

## Fluxo principal

```mermaid
flowchart LR
    U[Usuário] --> P[Portal CloudIFF]
    P --> F[Forgejo]
    P --> K[Komodo e runtime]
    P --> S[Supabase]
    A[Agente de IA] -->|OAuth 2.1 + MCP| M[Gateway MCP]
    M --> P
    P --> O[Auditoria e aprovações]
```

## Exemplo provisionado: Laboratório de Hardware

| Recurso | Endereço ou parâmetro |
|---|---|
| Repositório Forgejo | `https://cloudiff.duckdns.org/git/iff1742962/cloudif-laboratorio-de-hardware` |
| Clone HTTPS | `https://cloudiff.duckdns.org/git/iff1742962/cloudif-laboratorio-de-hardware.git` |
| Clone SSH esperado | `ssh://git@cloudiff.duckdns.org:2222/iff1742962/cloudif-laboratorio-de-hardware.git` |
| Portal/Studio do tenant | `https://iff1742962-laboratoriodehardware.cloudiff.duckdns.org` |
| URL pública Supabase | `https://iff1742962-laboratoriodehardware.cloudiff.duckdns.org` |
| MCP canônico da plataforma | `https://cloudiff.duckdns.org/cloudiff/mcp` |
| Pooler PostgreSQL | host `iff1742962-laboratoriodehardware.cloudiff.duckdns.org`, porta `54400`, banco `postgres` |
| Usuário do pooler | `postgres.iff1742962-laboratoriodehardware` |

Exemplo de string, sem senha:

```text
postgresql://postgres.iff1742962-laboratoriodehardware:[YOUR-PASSWORD]@iff1742962-laboratoriodehardware.cloudiff.duckdns.org:54400/postgres
```

> Senhas, tokens, chaves privadas e valores `.env` nunca devem ser publicados no Git. A porta PostgreSQL só deve ser exposta com VPN, allowlist ou TLS nativo no pooler.

## Conectar agentes MCP

O endpoint remoto é compartilhado pela plataforma; a autorização e as ferramentas são filtradas pela identidade e pela ACL de cada projeto.

```bash
claude mcp add --scope project --transport http \
  --client-id "<CLIENT_ID_DO_PROJETO>" --client-secret \
  cloudiff "https://cloudiff.duckdns.org/cloudiff/mcp"

claude mcp login cloudiff
```

Para integrações que também precisam da API Supabase do projeto:

```bash
export NEXT_PUBLIC_SUPABASE_URL="https://iff1742962-laboratoriodehardware.cloudiff.duckdns.org"
```

O `Client ID` e o `Client Secret` são emitidos na aba **Agentes de IA** para cada projeto. O segredo é solicitado de forma mascarada pelo Claude Code e não deve ser salvo no README. O fluxo OAuth aceita callbacks HTTPS conhecidos e callbacks locais temporários, como `http://127.0.0.1:<porta>/`, usados por clientes desktop. O callback local não precisa ser publicado no roteador.

## Acesso externo

A configuração completa de NAT, firewall, Forgejo, PostgreSQL, proxy reverso, MCP e testes está em [Acesso externo e conexões](docs/manual-tecnico/13-ACESSO-EXTERNO.md).

Resumo das portas públicas:

| Porta | Uso | Encaminhamento recomendado |
|---:|---|---|
| `443/tcp` | Portal, Forgejo HTTPS, Supabase HTTP e MCP/OAuth | proxy reverso público |
| `80/tcp` | desafio ACME e redirecionamento para HTTPS | proxy reverso público |
| `2222/tcp` | Git por SSH | Forgejo SSH interno |
| `54400/tcp` | PostgreSQL/Supavisor | somente com VPN/allowlist/TLS |

## Documentação técnica

Este repositório funciona também como uma apostila técnica da plataforma:

- [Manual técnico completo](docs/manual-tecnico/README.md)
- [Acesso externo e conexões](docs/manual-tecnico/13-ACESSO-EXTERNO.md)
- [Arquitetura e diagramas](docs/manual-tecnico/01-ARQUITETURA.md)
- [Runtime unificado de projetos](docs/manual-tecnico/11-RUNTIME-UNIFICADO.md)
- [Arquitetura operacional atual](docs/manual-tecnico/12-ARQUITETURA-OPERACIONAL-ATUAL.md)
- [Fluxos de processo](docs/manual-tecnico/02-FLUXOS.md)
- [Agentes e funções](docs/manual-tecnico/03-AGENTES.md)
- [Protocolos de reconciliação](docs/manual-tecnico/04-RECONCILIACAO.md)
- [Modelo e dicionário de dados](docs/manual-tecnico/05-DADOS.md)
- [Mensagens, aprovações e segurança](docs/manual-tecnico/06-MENSAGENS-E-APROVACOES.md)
- [Catálogo de agentes](docs/CATALOGO-DE-AGENTES.md)
- [Catálogo de serviços](docs/CATALOGO-DE-SERVICOS.md)
- [Catálogo de rotas](docs/CATALOGO-DE-ROTAS.md)
- [Inventário de todos os arquivos](docs/INVENTARIO-DE-ARQUIVOS.md)

## Componentes versionados

Este snapshot reúne o código-fonte e as configurações versionáveis dos três nós da plataforma:

- **control-plane**: Portal, MCP, AuthZ, tenant guard, reconciliadores, monitores e testes;
- **runtime**: Komodo, agentes, stacks e serviços de execução;
- **proxy**: proxy reverso, configurações customizadas e automações;
- **tenant-templates**: templates, scripts, testes e composições dos tenants Supabase.

## Vídeos de apresentação

- [Apresentação rápida da CloudIFF](https://youtu.be/cxH3K8s1R9M)
- [Demonstração prática da plataforma](https://youtu.be/pJ7mx3VZuWU)

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

Este repositório não contém senhas, tokens, chaves privadas, arquivos `.env`, certificados, bancos, logs, backups, volumes ou snapshots publicados. Valores sensíveis devem ser injetados por variáveis de ambiente ou pelo gerenciador de segredos da infraestrutura.

## Validação e manutenção

Antes de enviar alterações:

```bash
scripts/validate.sh
```

Consulte [Manutenção](docs/MAINTENANCE.md), [Auditoria do repositório](docs/REPOSITORY_AUDIT.md), [Cobertura](docs/COVERAGE_AUDIT.json) e [Inventário](docs/INVENTORY.json).

## Portal v2

A migração incremental do Portal está em `portal/`. Consulte o [plano de aperfeiçoamento](docs/portal-v2/PLANO-DE-APERFEICOAMENTO.md), o [guia de migração](docs/portal-v2/GUIA-DE-MIGRACAO.md) e o [protótipo](docs/portal-v2/prototipo.html). O Portal legado permanece como fallback até a promoção individual das rotas.

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
