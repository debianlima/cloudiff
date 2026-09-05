# Superfícies congeladas

As telas abaixo estão homologadas e não devem receber alterações estruturais sem solicitação explícita e atualização dos testes de contrato:

- Visão geral
- Publicações
- Projetos
- Bancos e tenants

## Contrato de Bancos e tenants

Devem permanecer preservados:

- agrupamento **Meus bancos**;
- serviços detectados em painel recolhível e compacto;
- permissões em painel recolhível;
- autocomplete ligado ao provedor de identidade;
- bloqueio de inclusão sem identidade validada;
- proprietário exibido como **Dono do banco**;
- proprietário sem ação de remoção;
- bloqueio de remoção também no backend;
- mensagens visíveis para identidade inexistente ou falha de consulta.

Alterações futuras devem ser pontuais, acompanhadas por testes e sem modificar as superfícies congeladas adjacentes.
## Navegação principal

A navegação principal deve expor **Aprovações** diretamente em **Painel geral**. A página também pode permanecer no contexto de projeto, mas o acesso ao gate humano não pode depender de o usuário descobrir primeiro uma rota contextual ou um atalho secundário. Esta exceção estrutural foi solicitada explicitamente na homologação U11 de 2026-09-04.
## Aprovações — tema e histórico

A página **Aprovações** mantém o item principal e a navegação contextual já homologados. No tema escuro, o item contextual ativo deve usar os tokens canônicos do IFF (`--iff-wash`/`--iff-dark`) em vez de variáveis legadas indefinidas. Registros históricos não permanecem expandidos no fluxo principal: **Carregar histórico** abre uma janela modal, deixando pendências e **Sempre permitir** imediatamente acessíveis. Esta alteração visual/ergonômica foi autorizada explicitamente na U15 de 2026-09-04.
## Navegação contextual — Reconciliação, Código e Produção

Os links já existentes em **Reconciliação** não mudam de rota nem função. O estado ativo da navegação contextual usa os tokens globais `--iff-wash`/`--iff-dark` em todos os contextos. Quando o tema escolhido é **Escuro**, o shell canônico continua usando `--paper`/`--ink`. A negativa de acesso a **Produção** preserva HTTP 403 e a mesma autorização, mas é adaptada ao shell canônico em vez de expor a página legacy. Emenda visual autorizada na U16 de 2026-09-04.
### Código — chips e estados no tema escuro

Na aba **Código**, identificadores `<code>` e badges de estado do módulo legado acompanham o mesmo bridge dark dos cards: identificadores usam `--surface-2`/`--ink-2`; estados positivos usam `--iff-wash`/`--iff-dark`; estados neutros usam `--surface-2`/`--ink-2`. A mudança é limitada a `.tab-git .legacy-content` e foi autorizada na U17 de 2026-09-04.

## Conectores — Conexões remotas (U19)

A superfície congelada de **Conectores** recebe somente um botão adicional, **Conexões remotas**. O botão abre um `<dialog>` sobre a página existente; não cria item de navegação, não substitui cards atuais e não rearranja a arquitetura de informação. O diálogo apresenta o gateway único `:443`, chave temporária entregue uma vez e instruções de túnel por projeto. Nenhuma porta de serviço é exposta diretamente. Esta exceção mínima foi autorizada explicitamente pelo operador em 2026-09-04.
