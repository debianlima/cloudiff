# PGH — Identidades, competências e roteamento CloudIFF

Observação: 14/11/2026. Fonte: catálogo PGH v2 ao vivo no LabIFF.
O catálogo é dinâmico; este documento não é a fonte de opções fixas do plugin.

| Área | Código | Responsabilidade |
| --- | --- | --- |
| auditoria | aud-01 | Auditoria, evidências, segurança, backups, gates e reauditoria |
| desenvolvimento | dev-01 | Código funcional, bugs de backend, interfaces e integrações |
| desenvolvimento | dev-02 | GitHub, Forgejo, SCM, CI, releases e integração Atlas |
| documentacao | doc-01 | Atlas, manuais, runbooks, inventários e memória persistente |
| infraestrutura | infra-01 | PHP, SO, CVEs, SSH, firewall, containers, proxy, TLS e serviços |
| testes | surface-01 | Testes visuais em navegador: telas, menus, botões, dados e regressão |

Há também a identidade documentacao/dotfiles/doc-01, de manutenção Dotfiles.
As seis identidades da tabela pertencem ao projeto cloudiff. Novos agentes
devem ser descobertos na memória PGH, nunca inferidos da lista histórica.

## Retomada obrigatória

No host controlador autorizado, conferir hostname, usuário e permissões.
Consultar o catálogo vivo com:

    python3 /srv/mcp-workspace/cloudiff-admin/agent-memory-v2.py catalog --json

Para infra-01:

    python3 /srv/mcp-workspace/cloudiff-admin/agent-memory-v2.py resume --area infraestrutura --project cloudiff --code infra-01

Para surface-01:

    python3 /srv/mcp-workspace/cloudiff-admin/agent-memory-v2.py resume --area testes --project cloudiff --code surface-01

Ler PROJECT, TASKS, ACCESS, MEMORY, HISTORY e o roteiro operacional de cada
agente. Respeitar tarefa, dependências, leases, privilégios reais e backlog.

## Distribuição de defeitos

1. Reproduzir ou identificar o achado, ambiente, data, gravidade e evidência.
2. Registrar nota na memória PGH da identidade de origem e obter seq de evento.
3. Aud-01 distribui auditorias usando audit-dispatch.
4. Infra-01 e surface-01 usam finding-dispatch para encaminhar erros
   aos agentes da área correta, vinculando tarefa existente quando possível.
5. Dev-01 recebe bugs funcionais; dev-02 recebe CI, Git, publicação e Atlas.
6. Infra-01 recebe problemas de rede, servidores, PHP, CVE e firewall.
7. Surface-01 valida correções do ponto de vista do usuário, em navegador
   e conta autorizados. Sem navegador, registrar bloqueio, não afirmar teste.
8. Doc-01 mantém Atlas e documentação rastreáveis. Aud-01 valida os gates.

O despacho atualiza memória e tarefas, mas não inicia sessão de chat,
não concede root e não executa automaticamente uma correção em produção.
As ações devem ser autorizadas, com backup/restauração quando necessário,
regressão e rollback verificáveis. Não registrar segredos em memória/Git.

## Contrato Atlas para humanos

Cada agente é uma ficha de ferramenta com identidade estável, área,
missão, vínculo com CloudIFF e referência ao roteiro PGH no LabIFF.
O PGH permanece a fonte de verdade para tarefas e handoffs; Atlas é índice.

Cadastros verificados na API do Atlas em 14/11/2026:
- pgh.agent.auditoria.cloudiff.aud_01
- pgh.agent.desenvolvimento.cloudiff.dev_01
- pgh.agent.desenvolvimento.cloudiff.dev_02
- pgh.agent.documentacao.cloudiff.doc_01
- pgh.agent.infraestrutura.cloudiff.infra_01
- pgh.agent.testes.cloudiff.surface_01
- pgh.agent.documentacao.dotfiles.doc_01 (identidade adicional Dotfiles)

Na primeira operação, a API passou de 213 a 215 itens com infra-01 e surface-01.
Na segunda, 223 itens foram preservados e cinco fichas foram acrescentadas,
resultando em 228 no instante da verificação; as demais alterações entre as
coletas pertencem a outros processos. Ambas as operações têm exportação API,
backup do grafo e auditoria de resultado no servidor IPsec. O valor total não
é fixo e precisa ser consultado novamente para auditorias posteriores.

## Publicação e aceite

Código funcional sob desenvolvimento requer branch própria, testes, revisão,
CI remoto e autorização. Segurança e Surface revisam resultados após a
correção. Documentação mantém fonte e timestamp, distingue estados
administrativos de saúde real e registra URLs/digests confirmados.
Novos projetos ou agentes devem gerar reconciliação Atlas, documentos e PGH.

Fontes internas LabIFF:
- agent-memory/v2/areas/infraestrutura/projects/cloudiff/agents/infra-01/ROTEIRO-OPERACIONAL.md
- agent-memory/v2/areas/testes/projects/cloudiff/agents/surface-01/ROTEIRO-OPERACIONAL.md
- agent-memory/v2/areas/auditoria/projects/cloudiff/agents/aud-01/ROTEIRO-OPERACIONAL.md

Ver também ATLAS-CLOUDIFF-PGH-OPERACAO.md e ATLAS-CLOUDIFF-CONCILIACAO.md.

## Autorizações condicionadas de 15/11/2026

O protocolo PGH-AUT-20261115-001 distribuiu 13 pedidos a infra-01, dev-01, dev-02, aud-01 e surface-01, sem duplicar tarefas. Autorizar condicionalmente não comprova um gate nem concede privilégios irrestritos. Ver [matriz de responsáveis e condições](PGH-AUTORIZACOES-CLOUDIFF-2026-11-15.md). A memória PGH no LabIFF permanece canônica.
