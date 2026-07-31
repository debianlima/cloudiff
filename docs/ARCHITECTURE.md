# Arquitetura resumida

## Control plane

Responsável por Portal, autorização, tenants, onboarding, MCP, monitoramento, reconciliação, publicação e auditoria.

## Runtime

Responsável por Komodo, agentes, stacks, containers, builds e execução dos projetos.

## Proxy

Responsável por entrada HTTPS, roteamento público, certificados e encaminhamento para serviços internos.

## Tenants

Cada tenant Supabase utiliza templates versionáveis. Dados e credenciais do tenant não fazem parte deste repositório.
