# Arquitetura

## Visão lógica

```mermaid
flowchart LR
  U[Usuário] --> A[Authentik / SSO]
  A --> P[Portal CloudIFF]
  AI[ChatGPT / Claude / Llama] --> O[OAuth 2.1 / MCP]
  O --> M[MCP Gateway]
  P --> CP[Serviços do plano de controle]
  M --> CP
  CP --> AR[Registro de agentes]
  CP --> AP[Aprovações humanas]
  CP --> RC[Reconciliação e transações]
  CP --> FA[Agente Forgejo]
  CP --> KA[Agente Komodo]
  CP --> SA[Serviços Supabase]
  CP --> PA[Agente do proxy]
  FA --> F[Forgejo]
  KA --> K[Komodo / Docker]
  SA --> T[Tenants Supabase]
  PA --> N[Nginx Proxy Manager]
  K --> PUB[Publicações]
  N --> PUB
  CP --> DB[(SQLite de controle)]
  CP --> AU[(Auditoria)]
```

## Distribuição física

```mermaid
flowchart TB
  subgraph H[Host de hospedagem / plano de controle]
    Portal[Portal :18094]
    MCP[MCP Gateway]
    Services[APIs, brokers, reconciliadores]
    Tenants[Tenants Supabase]
    Router[Roteador de tenants :8099]
    State[(Bancos e jobs)]
  end
  subgraph R[Host runtime / forja]
    Forgejo[Forgejo]
    Komodo[Komodo]
    ForjaAgent[Forja Agent]
    KomodoAgent[Komodo Agent]
    Apps[Stacks e publicações]
  end
  subgraph X[Host proxy]
    NPM[Nginx Proxy Manager]
    ProxyAgent[Publisher Agent]
  end
  Portal --> Services
  MCP --> Services
  Services <--> ForjaAgent
  Services <--> KomodoAgent
  ForjaAgent --> Forgejo
  KomodoAgent --> Komodo
  Komodo --> Apps
  Services --> Tenants
  NPM --> Router
  NPM --> Apps
  ProxyAgent --> NPM
  Services <--> ProxyAgent
  Services --> State
```

## Fronteiras de responsabilidade

| Camada | Responsabilidade |
|---|---|
| Portal | Experiência humana, validação de formulário, acompanhamento e ações diretas. |
| MCP Gateway | Protocolo MCP, OAuth, descoberta de ferramentas e identidade do agente. |
| Brokers | Planos e efeitos controlados para build, deploy, preview, workspace e Supabase. |
| Registro de agentes | Client ID, hash do segredo, escopos, projeto e limites. |
| Aprovações | Decisões humanas para ações protegidas e ativação de produção. |
| Reconciliação | Comparar estado desejado e observado e executar correções idempotentes. |
| Agentes runtime | Adaptar APIs centrais a Forgejo, Komodo, Docker e filesystem local. |
| Proxy | Publicar rotas, certificados e nomes estáveis/versionados. |
| Tenants Supabase | Banco, Auth, REST, Storage, Realtime, Studio e serviços auxiliares por tenant. |

## Runtime de cada projeto

Cada projeto novo possui um container exclusivo com Apache, PHP e Node.js. As imagens-base são compartilhadas por combinação de versões; os processos e arquivos do projeto não são compartilhados. O proxy público termina TLS em 80/443 e encaminha HTTP interno para a porta 80 do Apache.
