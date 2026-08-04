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
