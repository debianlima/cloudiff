# CloudIFF — fechamento global W→H→P, refresh, histórico e retenção

**Data:** 21/11/2026. **Escopo:** todos os projetos CloudIFF.

## Invariantes

1. Forgejo atualiza um Preview fixo; não cria novo W por commit.
2. W→H clona o runtime saudável corrente. Código/imagens/origem Forgejo ficam congelados; variáveis H podem ser alteradas explicitamente e esse estado configurado é o que será homologado.
3. H→P promove a mesma instância/deployment, sem rebuild/reclone.
4. H publicada deixa de ser ambiente ativo. Site/Terminal/Variáveis de H só existem para H `awaiting_homologation` ou `homologated` compatível.
5. Variáveis pertencem ao estágio e herdam W→H→P. Alterações posteriores são mutações explícitas do estágio escolhido.
6. Jobs de H, P e rollback emitem refresh terminal para o modal de Ambiente de publicação.
7. Histórico de Produção reativa P anterior com prepare/health/route/cutover/commit; a P atual só é desligada depois do sucesso.
8. Bridges/rotas antigas são reconstruíveis e devem ser removidas quando inativas. Produções antigas podem manter containers/volumes parados enquanto necessários ao rollback exato.
9. H residual deve ser zero fora de uma homologação realmente ativa.
10. Registros e docs antigos `dN`/rebuild permanecem somente como histórico, não como prescrição atual.

## Deltas live a9/Compose

A árvore live ainda carrega proveniência a9/Compose não integralmente normalizada na árvore-base. Portanto os deltas abaixo são parte da fonte de release e não devem ser substituídos por cópia cega do arquivo live:

- `cloudiff-whp-history-executor-reactivation.patch`
- `cloudiff-whp-history-broker-reactivation.patch`
- `cloudiff-whp-history-komodo-gateway.patch`
- `cloudiff-whp-history-portal-runtime.patch`
- `cloudiff-whp-history-portal-shared.patch`
- `cloudiff-whp-ui-refresh-history.patch`
- `cloudiff-whp-ui-outer-refresh.patch`
- `cloudiff-whp-help-current-flow.patch`

Eles se somam aos patches anteriores de clone/promoção/variáveis por estágio. Reconciliar em ordem de base/proveniência, com `git apply --check` e reprodução por hash antes de atualizar um componente canônico.

## Provas executadas

- Agenda humano: W1 → H7 → mesma instância P7, revisão `18416127cdf9`.
- Publisher P1020: somente W1 e P7 roteados.
- P6 histórico: `prepare` iniciou os três serviços, health passou, `abort` parou os mesmos serviços; containers não foram recriados e volumes foram preservados; P7 permaneceu saudável.
- P2 legado: container histórico iniciou saudável sem possuir alias ativo e voltou a parar; P7 permaneceu saudável.
- UI headless: criar H, publicar P e rollback emitiram `cloudif:publication-state-changed` ao job `succeeded`; Histórico exibiu `Reativar P6` e fez POST no endpoint correto.
- Suíte canônica relevante: 48/48 testes PASS.

### Refresh terminal da interface

Ao concluir com sucesso a criação de H, a promoção H→P ou a reativação histórica, o Portal atualiza o workspace do ambiente e executa recarregamento completo da página. Falhas não recarregam automaticamente: a mensagem de erro permanece visível para diagnóstico. Isso evita depender de F5/manual refresh para exibir o estágio recém-concluído.

### Identidade fixa do Preview Wn e histórico de Produção

O Preview é fixo por projeto, mas o número do slot deve **preservar a identidade já existente**. Projetos novos podem iniciar em W1; projetos existentes não podem ser achatados/renumerados para W1. O sistema obtém o Wn canônico do histórico do projeto e mantém URL/bridge coerentes. Para o Agenda P1020, o slot canônico é **W3** (`1020-w3-preview.cloudiff.duckdns.org`).

Produções anteriores permanecem **Offline** por padrão. O Histórico separa três ações:

- **Subir**: liga o runtime histórico e publica somente a URL Pn para teste; não toca no endereço principal;
- **Desligar**: remove rota/bridge versionada e para o runtime, preservando containers/volumes necessários ao rollback;
- **Ativar no endereço principal**: somente quando a versão histórica está online/saudável, executa o cutover do domínio estável e só então desativa a Produção anterior.

O estado Online/Offline deve vir do runtime real, não apenas do banco do Portal. Uma P histórica online não significa Produção ativa. Apenas `is_active=1` + alias estável validado representam a Produção principal.
