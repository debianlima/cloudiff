# Fluxos de processo

## Criação e provisionamento de projeto

```mermaid
sequenceDiagram
  actor U as Usuário
  participant P as Portal
  participant J as Worker de provisionamento
  participant F as Forgejo Agent
  participant K as Komodo Agent
  participant S as Supabase
  participant O as Onboarding
  participant X as Proxy/Publicação

  U->>P: Envia wizard do projeto
  P->>P: Valida slug, runtime, PHP, tenant e permissão
  P->>P: Obtém lock project-<slug>
  P->>J: Grava job UUID e transfere lock
  J->>F: ensure-repo / webhook
  F-->>J: Repositório convergido
  J->>K: ensure project / stack
  K-->>J: Stack convergida
  J->>S: Obtém lock tenant-<tenant>
  J->>S: Cria ou repara tenant e aguarda 11 serviços
  S-->>J: Tenant saudável
  J->>O: Reconcilia identidades, capacidades e credencial
  O-->>J: Projeto pronto para agente
  J->>F: Publica somente o código-fonte na raiz do repositório
  J->>K: Gera runtime fora do Git e cria stack/container próprios de d1
  J->>X: Registra d1, valida URL versionada e promove o alias estável
  X-->>J: HTTP 200 em URL estável e versionada
  J-->>P: status=succeeded, step=complete
  P-->>U: Projeto provisionado
```

## Inclusão e remoção de membros

```mermaid
sequenceDiagram
  actor A as Administrador ou responsável
  participant P as Portal
  participant Q as Fila de reconciliação
  participant W as Worker
  participant F as Forgejo
  participant K as Komodo
  participant S as Supabase
  participant M as MCP

  A->>P: Adiciona ou remove pessoa do projeto ou banco
  P->>Q: project.membership.changed ou tenant.membership.changed
  Q->>W: Entrega estado desejado completo
  W->>F: Reconcilia colaborador do repositório
  W->>K: Reconcilia permissões e terminais de todas as dN
  W->>S: Reconcilia acesso ao tenant
  W->>M: Reconcilia identidade e integrações do projeto
  W-->>Q: Convergente ou retry com backoff
```

A operação é orientada ao estado atual, não apenas à ação incremental. Repetir o evento não duplica recursos; remover uma pessoa elimina somente os recursos individuais gerenciados pela CloudIFF e preserva o proprietário.

## Exclusão de tenant

```mermaid
flowchart TD
  A[Solicitação autenticada] --> B[Prévia e bloqueadores]
  B --> C{Confirmação exata?}
  C -- não --> Z[Interrompe sem efeito]
  C -- sim --> L[Lock tenant compartilhado]
  L --> D[Backup lógico final]
  D --> E[Arquivo de configuração]
  E --> F[Remove containers, volumes e rede]
  F --> G[Remove registry, ACL, políticas e metadados]
  G --> H[Remove diretório do tenant]
  H --> I[Renderiza e recarrega roteador]
  I --> J[Verifica resíduos em Docker, registry, Portal e onboarding]
  J --> K[Grava result.json e recibo durável]
  K --> M[Modal recupera succeeded mesmo durante reload]
```

## Publicação

```mermaid
stateDiagram-v2
  [*] --> Planejada
  Planejada --> Construindo: template aplicado
  Construindo --> Iniciando: docker compose build
  Iniciando --> Saudavel: healthcheck aprovado
  Saudavel --> Homologada: smoke HTTP 200
  Homologada --> Ativa: promoção aprovada
  Ativa --> Revertendo: rollback
  Revertendo --> Ativa: versão anterior restaurada
  Construindo --> Falha: build real falhou
  Iniciando --> Falha: runtime não estabilizou
  Homologada --> Falha: proxy ou smoke falhou
```

## Fluxos atuais complementares

Os fluxos de ACL, terminal compartilhado, publicação versionada e exclusão derivada estão detalhados em [Arquitetura operacional atual](12-ARQUITETURA-OPERACIONAL-ATUAL.md). Esse capítulo deve ser considerado o contrato vigente para integrações entre Portal, Forja Agent, Komodo Agent, Publisher e Tenant Guard.
