# Ciclo de migração v1 -> v2 (estado vivo)

## NO AR pela v2 (produção)
- **Visão geral (home)** — /cloudiff/portal e ?tab=resumo. Conteúdo real:
  saudação por perfil, atalhos, Servidores CloudIF (métricas ATUAIS da tabela
  node_metrics_cache), Informações da Plataforma. Nav de topo: "Início" ativo;
  demais itens "em breve" (desabilitados até serem portados).
- **GET /api/reconciliation** (API).

## Mecanismo
- Shim: /srv/cloudif/lib/cloudif_portal_v2_coexist.py (lista READY + assets + home só sem aba).
- Carga: .pth /usr/local/lib/python3.14/dist-packages/zz_cloudif_portal_v2.pth
  (import determinístico; o sitecustomize do sistema tinha precedência).
- Escopo: Environment=CLOUDIF_PORTAL_V2=1 no drop-in do unit do portal.
- IMPORTANTE: o serviço usa PrivateTmp=yes (logs de debug vão a /tmp isolado).

## REVERTER a home (volta ao legado)
Editar READY do shim removendo (/cloudiff/portal,GET) e (/cloudiff/portal/,GET),
ou remover o drop-in de env e reiniciar.

## PRÓXIMAS ITERAÇÕES (portar antes de linkar na nav)
Ordem: projects (Projetos) -> data (Bancos) -> delivery (Entrega) ->
environments (Produção) -> health (Saúde) -> admin (Administração).
Cada uma: portar conteúdo real (via legacy_bridge / extração), verificar
paridade de formato e acesso, adicionar a PORTED no shell + READY no shim,
promover com health-check e rollback.

Regressões conhecidas a corrigir ao portar:
- environments: aluno recebe 200 onde v1 dá 403 (production-operations).
- data/projects: dependem de user_visible_projects, docker ps, tenant registry.

## Iteração Projetos (em andamento)
- LEITURA: visible_projects portada e verificada IDÊNTICA à v1 (admin 8, prof 5,
  aluno 3, iff1860746 3). Cards renderizam no test server (18120) via
  /cloudiff/portal/pagina/projetos?perfil=...
- AÇÃO project_action(check/sync): portada (service.project_action) e VERIFICADA
  executando no sentinela sistema-de-biblioteca-teste:
  komodo_status running->checked, action_log +1 (project_check), rc=0. Idêntico à v1.
- Rota POST /action/project_action ligada com CSRF (guard authenticated, como a v1).
- FALTA em Projetos antes de promover a página: edit_save, create_project,
  publication, e as ações de reparo/terminal. Cada uma portada + verificada no
  sentinela, e só então a página vai ao ar e Projetos vira link na nav.
