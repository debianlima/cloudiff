# Agentes e funções

## Agentes de execução

| Agente | Local | Funções principais |
|---|---|---|
| Forja Agent | runtime | Criar repositório, webhook, branches, propostas, arquivos, commits, rollback, releases e status. |
| Komodo Agent | runtime | Criar projeto/stack, pull, build, deploy, rebuild, inspeção, reparo, terminal e publicações. |
| Artifact Executor | runtime | Construir artefatos imutáveis e registrar checksums. |
| Preview Executor | runtime | Executar previews isolados e temporários. |
| Production Canary Executor | runtime | Executar canário interno sem tráfego público. |
| Production Homologation Executor | runtime | Deploy e rollback de homologação com troca atômica. |
| Production Public Executor | runtime | Deploy e rollback público autorizado. |
| NPM Publisher Agent | proxy | Criar/atualizar hosts, certificados e rotas de publicação. |

## Serviços inteligentes do plano de controle

| Serviço | Papel |
|---|---|
| MCP Gateway | Expõe ferramentas, recursos e prompts; autentica por token direto ou OAuth 2.1. |
| Agent Registry | Mantém clientes, escopos, hashes de segredo, projetos e limites. |
| Agent Controller | Coordena tarefas e estado de agentes. |
| Approval API | Registra solicitações, decisões, aprovadores e dupla aprovação. |
| Workspace Broker | Prepara, valida, testa e edita workspaces. |
| Build Broker | Enfileira builds e entrega ao executor. |
| Preview Broker | Planeja e cria previews. |
| Deployment Broker | Planeja promoção, homologação, produção e rollback. |
| Runtime Policy | Detecta stack, valida runtime e produz plano homologado. |
| Project Onboarding | Reconcilia identidade, credencial, conectores e instruções MCP. |
| Project Capabilities | Calcula funções disponíveis por projeto e ambiente. |
| Reconcile Worker | Consome eventos e converge sistemas externos. |
| Transaction Reconciler | Recupera transações parciais e garante convergência. |

## Ferramentas MCP

As ferramentas são descobertas por `initialize`, `resources/list`, `resources/read`, `prompts/list` e `tools/list`. Cada chamada carrega:

- `client_id`;
- projeto vinculado;
- escopo solicitado;
- ambiente;
- identificador de correlação;
- política de aprovação;
- dados mínimos da operação.

Ferramentas de leitura podem executar diretamente. Ferramentas com efeito produzem plano e, quando protegidas, uma solicitação de aprovação antes de qualquer alteração.
