# Guia de migração — CloudIFF Portal v2

A migração ocorre por coexistência. O Portal legado permanece como fallback até
todas as rotas terem uma implementação v2 observada em produção.

## Estrutura

```text
portal/
├── app.py
├── registry.py
├── core/
├── design/
├── ui/
├── modules/
└── legacy/
```

A regra de dependência é:

```text
modules → ui → design
   └────→ core
```

Módulos não importam módulos irmãos. Toda rota declara `permission` antes de ser
registrada. Navegação e conteúdo protegido são filtrados antes da renderização.

## Coexistência

O registry começa vazio. `portal.app.handle()` envia qualquer rota desconhecida
para o handler legado. A migração avança uma rota por vez, sem corte único.

Ordem recomendada:

1. saúde;
2. administração;
3. dados;
4. entrega;
5. ambientes;
6. projetos;
7. visão geral.

Cada módulo passa por teste de permissão, comparação lado a lado, smoke e release
reversível. Para reverter um módulo, remova o registro da rota; o fallback volta
ao legado imediatamente.

## Design system

- valores de cor, tipografia, espaço e raio existem apenas em `tokens.css`;
- `components.css` não aceita `!important`;
- o verde institucional representa marca e convergência;
- âmbar representa deriva;
- vermelho representa falha;
- azul representa foco;
- nenhum elemento é escondido por busca de texto ou correção tardia em JavaScript.

## Antes do pull request

```bash
scripts/validate.sh
scripts/test.sh
```

O portão reprova segredo, símbolo redefinido, bloco CSS duplicado, aumento de
`!important`, cor literal fora dos tokens, importação entre módulos irmãos e rota
sem permissão.
