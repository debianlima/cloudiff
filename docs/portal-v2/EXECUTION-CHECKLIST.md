# Execução da migração do Portal v2

Este checklist é atualizado a cada promoção. O shell visual permanece fixo; a
migração avança pela integração das funções existentes.

## Concluído

- [x] Inventário de 30 abas do Portal legado.
- [x] Tabela observada de permissões e rotas.
- [x] Design system único (`tokens.css`, `base.css`, `components.css`).
- [x] Shell canônico com navegação lateral e cabeçalho único.
- [x] Navegação administrativa filtrada antes da renderização.
- [x] Implementação v2 ativa sincronizada para a fonte.
- [x] Adaptador de conteúdo legado com CSS confinado.
- [x] Preservação byte a byte do conteúdo funcional das abas.
- [x] Preservação de formulários, CSRF, IDs, links e scripts funcionais.
- [x] Remoção dos scripts que recriavam menu e contexto visual antigos.
- [x] Auto-recovery para resposta legada original em qualquer falha.
- [x] Ativação restrita ao serviço do Portal via `sitecustomize.py`.
- [x] Testes unitários de registry, permissões, shell e adaptação.
- [x] Zero `!important`, símbolos duplicados ou blocos CSS duplicados na v2.

## Promoção atual

- [ ] Todas as 30 abas respondem HTTP 200 no shell v2. *(validar após promoção)*
- [x] Conteúdo, formulários, CSRF, IDs e links de ação preservados em páginas reais.
- [ ] Perfis aluno, tenant, professor e administrador validados.
- [ ] APIs e downloads permanecem fora do adaptador visual.
- [ ] Smoke completo passa três vezes.
- [ ] Healthcheck, reconciliador e revisão de segurança passam.
- [ ] Rollback automático validado.

## Extração funcional progressiva

A apresentação já usa o shell v2. A lógica continua sendo extraída sem alterar o
layout, nesta ordem:

1. saúde e reparação;
2. administração;
3. dados;
4. entrega;
5. produção;
6. projetos;
7. visão geral.
