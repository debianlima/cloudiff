# Mensagens, aprovações e segurança

## Transporte de uma solicitação de agente

```mermaid
sequenceDiagram
  participant C as Cliente IA
  participant G as MCP Gateway
  participant R as Agent Registry
  participant B as Broker
  participant A as Approval API
  participant E as Executor
  participant U as Usuário

  C->>G: JSON-RPC + Bearer/OAuth
  G->>R: validar client_id, segredo, escopo e projeto
  R-->>G: autorização efetiva
  G->>B: ferramenta + trace_id
  B->>B: validar esquema e gerar plano
  alt leitura ou ação não protegida
    B->>E: executar
  else ação protegida
    B->>A: criar approval_id
    A-->>U: aparece no Portal
    U->>A: permitir, negar ou sempre permitir
    A-->>B: decisão vinculada ao plano
    B->>E: executar quando autorizada
  end
  E-->>B: resultado e evidências
  B-->>G: JSON estruturado
  G-->>C: resposta JSON-RPC
```

## Aceitação e rejeição

Uma decisão só é válida quando corresponde ao projeto, ação, solicitante, ambiente, hash do plano e prazo. A ativação real de produção exige dois aprovadores distintos e o solicitante não pode aprovar a própria ativação.

A opção **sempre permitir** deve criar uma regra revogável e específica, nunca uma permissão global implícita. A regra é avaliada antes de abrir uma nova solicitação e deve ser registrada na auditoria.

## OAuth e MCP

- Discovery: `/.well-known/oauth-authorization-server`.
- Recurso protegido: `/.well-known/oauth-protected-resource/cloudiff/mcp`.
- Authorization code com PKCE S256.
- Client ID é a identidade do agente/projeto.
- Client Secret é a chave gerada no Portal.
- Access token é temporário; refresh token é revogável.
- Token direto MCP continua suportado para clientes simples.
