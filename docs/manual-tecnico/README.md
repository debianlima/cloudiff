# Manual técnico da CloudIFF

Este manual descreve a CloudIFF como plataforma de ensino, provisionamento, publicação, bancos Supabase, automação por agentes e governança humana. Ele foi escrito a partir do código versionado neste repositório e deve ser lido junto ao [inventário completo](../INVENTARIO-DE-ARQUIVOS.md).

## Roteiro de estudo

1. [Visão geral e arquitetura](01-ARQUITETURA.md)
2. [Fluxos de processo](02-FLUXOS.md)
3. [Agentes e funções](03-AGENTES.md)
4. [Protocolos de reconciliação](04-RECONCILIACAO.md)
5. [Modelo de dados e dicionário](05-DADOS.md)
6. [Mensagens, aprovações e segurança](06-MENSAGENS-E-APROVACOES.md)
7. [Operação, falhas e recuperação](07-OPERACAO.md)
8. [Modelo de software e responsabilidades](08-MODELO-DE-SOFTWARE.md)
9. [Catálogo de serviços](09-SERVICOS.md)
10. [Como evoluir a plataforma](10-DESENVOLVIMENTO.md)

## Catálogos gerados do código

- [Agentes e aplicações](../CATALOGO-DE-AGENTES.md)
- [Serviços e timers](../CATALOGO-DE-SERVICOS.md)
- [Rotas e endpoints](../CATALOGO-DE-ROTAS.md)
- [Dicionário de dados estático](../DICIONARIO-DE-DADOS-ESTATICO.md)
- [Inventário de arquivos](../INVENTARIO-DE-ARQUIVOS.md)

## Princípios centrais

- O Portal e os agentes são superfícies independentes: compartilham serviços e políticas, mas não dependem da mesma interface de execução.
- Operações de efeito passam por plano, autorização, execução, auditoria e reconciliação.
- O estado desejado fica nos registros centrais; agentes convergem Forgejo, Komodo, Supabase, proxy e publicação para esse estado.
- A mesma operação pode ser retomada porque os adaptadores são idempotentes e os jobs mantêm estado persistente.
- Operações concorrentes em recursos diferentes podem ocorrer em paralelo; o mesmo projeto ou tenant usa locks exclusivos.

<!-- CLOUDIFF-AUTO-DOC:BEGIN -->

## Inventário automático de `docs/manual-tecnico`

Documentação técnica, inventários e evidências.

| Item | Tipo | Finalidade |
|---|---|---|
| [`01-ARQUITETURA.md`](01-ARQUITETURA.md) | `.md` | Documento técnico ou operacional. |
| [`02-FLUXOS.md`](02-FLUXOS.md) | `.md` | Documento técnico ou operacional. |
| [`03-AGENTES.md`](03-AGENTES.md) | `.md` | Documento técnico ou operacional. |
| [`04-RECONCILIACAO.md`](04-RECONCILIACAO.md) | `.md` | Documento técnico ou operacional. |
| [`05-DADOS.md`](05-DADOS.md) | `.md` | Documento técnico ou operacional. |
| [`06-MENSAGENS-E-APROVACOES.md`](06-MENSAGENS-E-APROVACOES.md) | `.md` | Documento técnico ou operacional. |
| [`07-OPERACAO.md`](07-OPERACAO.md) | `.md` | Documento técnico ou operacional. |
| [`08-MODELO-DE-SOFTWARE.md`](08-MODELO-DE-SOFTWARE.md) | `.md` | Documento técnico ou operacional. |
| [`09-SERVICOS.md`](09-SERVICOS.md) | `.md` | Documento técnico ou operacional. |
| [`10-DESENVOLVIMENTO.md`](10-DESENVOLVIMENTO.md) | `.md` | Documento técnico ou operacional. |

> Esta seção é gerada por `scripts/generate-directory-readmes.py`. Conteúdo manual fora dos marcadores é preservado.

<!-- CLOUDIFF-AUTO-DOC:END -->
