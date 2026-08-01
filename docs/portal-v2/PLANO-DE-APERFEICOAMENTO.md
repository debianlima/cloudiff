# Plano de aperfeiçoamento — CloudIFF Portal

## Diagnóstico congelado

O Portal legado cresceu por camadas de override. No início da migração, o arquivo
`cloudif_ui_components.py` possui 57 ocorrências de `!important` e uma redefinição
conhecida de `profile_mount()`. Esses valores formam o baseline: podem diminuir,
mas não aumentar.

## Princípios

1. uma fonte de verdade por conceito;
2. linguagem de quem usa, não nomes de tecnologia;
3. nada é escondido depois de renderizado;
4. toda mudança passa por código executável no CI;
5. migração incremental e reversível.

## Fases

### Fase 0 — rede de segurança

- testes offline executados pelo CI;
- testes de produção analisados no CI e executados no release gate;
- detectores de símbolos redefinidos e CSS duplicado;
- teto de `!important` congelado;
- snapshot legado imutável.

### Fase 1 — design system único

- `tokens.css`;
- `base.css`;
- `components.css`;
- `app.js` do shell;
- protótipo executável em `docs/portal-v2/prototipo.html`.

### Fase 2 — quebra do monólito

Extrair sete módulos, um por vez, mantendo fallback legado.

### Fase 3 — navegação por intenção

Projetos, Ambientes, Dados, Entrega, Saúde e Administração. O menu será gerado a
partir do registry e filtrado por permissão.

### Fase 4 — autorização

Centralizar RBAC, eliminar permissões inalcançáveis e testar cada combinação de
papel e ação.

### Fase 5 — escala e deriva

Consolidar persistência, APIs e detector contínuo de diferença entre Git e hosts.

## Estado atual

As Fases 0 e 1 estão implementadas. O registry continua vazio e o Portal legado
continua atendendo todo o tráfego. A próxima migração funcional deve começar pelo
módulo `health`.
