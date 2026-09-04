# Estado — 2026-09-04 — contrato v47

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a única alteração estrutural desta unidade foi a inclusão explícitamente solicitada de **Aprovações** em `Painel geral` da navegação principal.
- `teste-sofa` continua projeto descartável de QA do owner `iff1742962`, tenant `iff1742962-testesofa`, publicação estável 1010, Preview W3 saudável e candidato H2 homologado.
- Produção P2 permanece vinculada ao candidato H2 e exige autorização crítica humana com dois aprovadores distintos admin/professor.
- O owner `iff1742962` pode acompanhar a aprovação, mas não pode decidir: `can_decide=false` continua parte do gate.
- `Aprovações` permanece também na navegação contextual de projeto; o acesso primário adicional existe para descobribilidade e não altera RBAC.
- A skill de projeto vigente passa a `cloudiff@0.1.9`.

## Decisões superadas
- Manter `Aprovações` apenas em navegação contextual/atalhos secundários — superado após o usuário não conseguir localizar o gate P2 pela navegação normal.
- Considerar a existência da rota `?tab=aprovacoes` suficiente para homologar o fluxo humano — superado: o caminho de tela também precisa ser descobrível a partir da navegação principal.

## Decisões humanas pendentes
- H001 P2 de `teste-sofa`: autorização crítica vigente `apr_4f9b40c9a80a4611bdcf` está `pending`, sem primeiro ou segundo aprovador. Exige dois usuários humanos distintos com papel admin/professor.

## Decisões fechadas nesta emenda
- `Aprovações` é entrada permanente de `Painel geral` na navegação principal do Portal v2.
- A mesma rota continua presente no contexto de projeto para preservar o fluxo orientado ao ciclo de entrega.
- O contrato de interface avançou de v46 para v47 e `portal/FROZEN_SURFACES.md` registra a exceção estrutural explicitamente solicitada.
- A mudança de navegação não concede permissão de decisão; autorização continua sendo derivada do Approval Service e dos grupos Authentik.
- As referências PGH da skill foram reconciliadas até `9b951d0d2f68a3ead190741fd5e8b4d6cc8e0a84`; nenhuma das skills referenciadas mudou de conteúdo desde o marco anterior.

## Pendências técnicas não humanas
- Nenhuma pendência técnica de navegação permanece para o gate P2.
- Após H001 ser satisfeita, ainda resta `production/enqueue`, convergência de P2, validação do artefato/HTTPS/terminal e rollback real para P1.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — vazio após o fechamento da U11; nenhuma zona de exclusão permanece reservada.

## Competências ativas nesta unidade
- `cloudiff@0.1.9` — skill raiz, atualizada com L019 após homologação real do caminho de navegação.
- `desenvolvedor-de-software@15` — método PGH vigente.
- `github-incremental-reconciliation@7` — reconciliação incremental antes do fechamento.
- `governanca-ontologica-de-skills@1.0.5` — política vigente.
- `telemetry-data-visualization@2` — macro global obrigatória.

## Falhas de portão por tipo de entrada
- `interface/navegacao`: o usuário não encontrou a aprovação P2 pela navegação normal; a barra principal não expunha `Aprovações`, embora a rota e a solicitação existissem.

## Divergências da última reconciliação
### Corrigidas
- `portal/ui/shell.py`: `Painel geral` passou a incluir `Aprovações` diretamente.
- Testes de arquitetura foram emendados para exigir a presença global da rota sem remover a navegação contextual.
- `portal/FROZEN_SURFACES.md`: contrato de navegação atualizado sob autorização explícita do operador.
- Deploy ativo: `/srv/cloudif/lib/portal` aponta para `u11-approvals-nav-d824ff6-20260904`.
- Reteste de tela real como `iff1742962`: página Projetos HTTP 200 contém link primário único para `?tab=aprovacoes`; página Aprovações HTTP 200 marca `Aprovações` com `aria-current=page`.
- A autorização P2 expirada da unidade anterior foi renovada pelo endpoint oficial; nova autorização `apr_4f9b40c9a80a4611bdcf` está `pending`, P2 continua sendo `publicationNumber=2`.
- A solicitação pendente aparece no HTML da página Aprovações e no endpoint independente `/api/approvals`.
- Owner continua `can_decide=false`, provando que a correção de descobribilidade não abriu bypass de autorização.

### Pendentes de autorização
- H001: primeiro e segundo aprovadores humanos distintos admin/professor ainda não decidiram a P2.

## Entradas aceitas nesta unidade
- 1352 — shell principal: `Aprovações` descobrível em `Painel geral`.
- 1228 — contrato de arquitetura da navegação principal atualizado.
- 1247 — contrato de navegação contextual preservado e reconciliado com o link global.
- `portal/tests/test_legacy_shell.py` — conjunto esperado de rotas normalizadas atualizado.
- `portal/FROZEN_SURFACES.md` — emenda explícita da superfície congelada.
- `skills/cloudiff/SKILL.md` — L019 e versão 0.1.9.
- `competencias.yaml` — versão da skill e referências PGH reconciliadas.

## Portões da unidade
- `NAVIGATION_CONTRACT_TESTS=PASS`: 30/30 testes de navegação, shell e superfícies congeladas.
- `LIVE_APPROVALS_NAVIGATION=PASS`: rota primária visível e estado ativo correto na página Aprovações.
- `PENDING_APPROVAL_UI=PASS`: nova P2 pendente aparece na UI e na API independente.
- `RBAC_UNCHANGED=PASS`: owner pode visualizar, mas `can_decide=false`.
- `PY_COMPILE=PASS`, `DIFF_CHECK=PASS`, `SECRET_SCAN=PASS`.
- `DELTA_INVENTORY=PASS` e `LEARNING_PRESERVED=PASS`: referências do catálogo verificadas sem delta de conteúdo nas skills consumidas.

## Próxima unidade
- Aguardar as duas decisões humanas de H001; após ambas, executar P2, smoke completo de Produção e rollback real para concluir a homologação do fluxo de aprovação/publicação.
