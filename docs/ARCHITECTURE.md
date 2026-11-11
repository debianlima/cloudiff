# Arquitetura resumida

## Control plane

Responsável por Portal, autorização, tenants, onboarding, MCP, monitoramento, reconciliação, publicação e auditoria.

## Runtime

Responsável por Komodo, agentes, stacks, containers, builds e execução dos projetos.

## Proxy

Responsável por entrada HTTPS, roteamento público, certificados e encaminhamento para serviços internos.

## Tenants

Cada tenant Supabase utiliza templates versionáveis. Dados e credenciais do tenant não fazem parte deste repositório.

## Estado operacional vigente

Os fluxos implementados de provisionamento, ACL, entrega **W → H → P**, terminal do Preview e exclusão derivada estão consolidados em [Arquitetura operacional atual](manual-tecnico/12-ARQUITETURA-OPERACIONAL-ATUAL.md). O contrato de publicação está detalhado em [Fluxo W → H → P](FLUXO-WHP-PUBLICACAO.md).
## Arquitetura modular obrigatória

O CloudIFF adota modularidade como requisito estrutural. Cada componente deve ter uma responsabilidade principal e uma interface explícita. Arquivos de entrada/orquestração devem coordenar módulos, não concentrar parsing, renderização, acesso a dados, regras de negócio e integrações no mesmo arquivo.

Novas funcionalidades devem nascer em módulos próprios quando não houver responsabilidade compatível já existente. Ao evoluir código legado grande, a preferência é extrair a responsabilidade tocada para um módulo coeso e testável, mantendo wrappers apenas quando necessários para compatibilidade. A mesma regra vale para Python e C++: migração de linguagem não autoriza recriar um monólito nativo.

## Interface e agentes — invariantes operacionais 2026-11

A auditoria de 2026-11-11 está em [`AUDITORIA-INTERFACE-E-AGENTES-2026-11-11.md`](AUDITORIA-INTERFACE-E-AGENTES-2026-11-11.md).

A interface v2 mantém as superfícies homologadas, mas carrega dados caros por disclosure/master-detail em vez de renderizar todos os detalhes no primeiro paint. Foco de teclado e seleção são estados distintos; seleção que dispara rede exige ativação explícita.

O agente-base C++ é a autoridade de heartbeat de nó. Serviços especializados (`--publisher`, `--artifact-executor`, `--runtime-executor`, `--mcp-upload`, `--secure-distribution`, `--admin-observability`) não substituem o heartbeat do agente-base. Saúde do agente exige sessão NATS + retomada de heartbeat, não apenas processo especializado ativo.

Rotas máquina-a-máquina não podem depender de `remote_addr` depois de uma bridge/proxy que perde a origem real. Controles de origem devem permanecer em uma camada com peer confiável; tokens/capabilities continuam necessários como autorização independente. Nunca ampliar allowlist para o IP genérico da bridge Docker como atalho.
