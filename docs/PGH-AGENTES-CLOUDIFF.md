# PGH — Identidades, competências e roteamento CloudIFF

Observação: 14/11/2026. Fonte: catálogo PGH v2 ao vivo no LabIFF.
O catálogo é dinâmico; este documento não é a fonte de opções fixas do plugin.

| Área | Código | Responsabilidade |
| --- | --- | --- |
| atendimento-usuario | atd-01 | Atendimento, orientação de usuários, coleta de solicitações e encaminhamento aos especialistas |
| auditoria | aud-01 | Auditoria, evidências, segurança, backups, gates e reauditoria |
| desenvolvimento | dev-01 | Código funcional, bugs de backend, interfaces e integrações |
| desenvolvimento | dev-02 | GitHub, Forgejo, SCM, CI, releases e integração Atlas |
| documentacao | doc-01 | Atlas, manuais, runbooks, inventários e memória persistente |
| governanca | gov-01 | Política, autorizações, exceções, gates e coerência do contrato PGH |
| infraestrutura | infra-01 | Segurança/infra principal, SO, CVEs, SSH, firewall, containers, proxy, TLS e serviços |
| infraestrutura | infra-02 | Diagnóstico e correções de infraestrutura delegadas/subtarefas, respeitando escopo PGH |
| infraestrutura | infra-03 | Projetos/migrações de infraestrutura especializados e integrações delegadas |
| testes | surface-01 | Testes visuais em navegador: telas, menus, botões, dados e regressão |

Há também a identidade documentacao/dotfiles/doc-01, de manutenção Dotfiles.
As dez identidades da tabela pertencem ao projeto cloudiff na leitura de 21/11/2026. Novos agentes
ou mudanças de identidade devem ser descobertos na memória PGH, nunca inferidos desta lista histórica.

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

Atd-01 recebe dúvidas/solicitações humanas, explica o fluxo padrão e encaminha execução técnica à área competente; não assume autoridade de deploy, rollback ou exceção.

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

Identidades PGH atuais que o Atlas deve reconciliar. Parte do conjunto foi verificada historicamente na API a partir de 14/11/2026; identidades adicionadas depois não devem ser declaradas publicadas até readback do Atlas:
- pgh.agent.atendimento_usuario.cloudiff.atd_01
- pgh.agent.auditoria.cloudiff.aud_01
- pgh.agent.desenvolvimento.cloudiff.dev_01
- pgh.agent.desenvolvimento.cloudiff.dev_02
- pgh.agent.documentacao.cloudiff.doc_01
- pgh.agent.governanca.cloudiff.gov_01
- pgh.agent.infraestrutura.cloudiff.infra_01
- pgh.agent.infraestrutura.cloudiff.infra_02
- pgh.agent.infraestrutura.cloudiff.infra_03
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

## Regra de retomada W/H/P — 20/11/2026

Todos os agentes que atuarem em Forgejo, Preview, Homologação, Produção, Komodo ou publicação devem ler [`PADRAO-CLOUDIFF-PREVIEW-HOMOLOGACAO-PRODUCAO-20261120.md`](PADRAO-CLOUDIFF-PREVIEW-HOMOLOGACAO-PRODUCAO-20261120.md) antes de executar mudanças. O contrato é global para CloudIFF.

### Checklist de retomada W/H/P — 21/11/2026

Ao retomar qualquer trabalho de publicação CloudIFF, o agente deve assumir e comprovar este contrato antes de alterar runtime:

1. **W é fixo:** Forgejo atualiza o mesmo Preview/URL; não criar W2/W3 por commit.
2. **W→H clona o runtime:** H nasce do Preview saudável corrente, não de rebuild do Git. Código/origem ficam congelados; variáveis H podem ser alteradas deliberadamente pelo usuário.
3. **H→P promove a mesma instância:** não rebuildar/reclonar. H deixa de ser ambiente ativo depois da promoção.
4. **Variáveis pertencem ao estágio:** W→H→P herda a configuração corrente; edição posterior atua somente no estágio selecionado. Secrets usam referências próprias e nunca são exibidos.
5. **Refresh terminal:** concluir H/P/rollback deve atualizar automaticamente o modal; não exigir clique manual em Atualizar.
6. **Retenção:** zero H residual; bridges/rotas antigas são reconstruíveis; P anterior fica parada enquanto for necessária para rollback exato.
7. **Histórico:** rollback prepara e valida a P histórica antes do cutover; se containers/estado persistente necessários não existirem, bloquear em vez de reconstruir silenciosamente do Forgejo.
8. **Fonte canônica:** ler o padrão W/H/P, `estado.md`, PGH/Atlas e patches de compatibilidade vigentes antes de normalizar componentes a9/Compose.

Registros antigos com “dN independente”, “H isolada permanente”, “rebuild de Produção” ou “novo container P a partir de snapshot” são históricos e não prescrevem o fluxo atual.
