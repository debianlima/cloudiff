# CloudIFF — contrato de variáveis por estágio e autoridade do runtime

**Vigência operacional:** 21/11/2026. **Escopo:** todos os projetos CloudIFF que usam Preview → Homologação → Produção.

## Regra de autoridade

Variável de ambiente é **estado do estágio/runtime**. O Portal não mantém uma configuração abstrata desacoplada do container:

- `preview`: leitura e escrita representam o Preview ativo;
- `homologation`: leitura e escrita representam a Homologação ativa; sem H ativa, a edição é bloqueada;
- `production`: leitura e escrita representam a Produção ativa; sem P ativa, a edição é bloqueada.

O Project Config Controller é o catálogo/auditoria da configuração, mas uma alteração aprovada só é considerada concluída quando o runtime daquele estágio confirma a aplicação. O reconciler assíncrono é retry, não fonte paralela de verdade.

## Herança W → H → P

1. Ao criar uma Homologação, a configuração corrente do Preview é promovida para `homologation` antes do clone. Valores públicos são copiados; secrets recebem novas referências próprias no ambiente de destino sem persistir plaintext no Portal.
2. O runtime H é o clone integral do Preview naquele instante e fica congelado em relação a mudanças posteriores do Forgejo/Preview.
3. Se o usuário editar variáveis da H, a alteração é aplicada ao deployment H ativo.
4. Ao promover H para Produção, a configuração corrente da H é promovida para `production` antes do cutover. A promoção H→P continua usando o **mesmo deployment homologado**, sem rebuild/reclone.
5. Se o usuário editar variáveis depois da promoção, a alteração é aplicada à Produção ativa.

## Mutação de variáveis em Docker

Docker não altera `Config.Env` de um container existente. Portanto uma edição explícita de variável pode substituir/recriar **somente os containers dos serviços afetados**, preservando:

- `deployment_id` do estágio;
- snapshot aprovado;
- volumes persistentes;
- redes e identidade lógica do deployment;
- serviços não afetados.

A promoção H→P em si **não recria containers**. Uma recriação posterior só ocorre como consequência explícita de uma edição feita pelo usuário.

A reconfiguração é fail-closed: o container anterior é mantido como backup temporário até o novo ficar saudável; em falha, o anterior é restaurado.

## PostgreSQL persistente

`POSTGRES_DB`, `POSTGRES_USER` e `POSTGRES_PASSWORD` não podem ser tratados como troca simples de `Env` depois que existe volume PostgreSQL persistente. Alterar apenas o container criaria divergência entre env e estado interno do banco.

Enquanto não houver uma operação transacional própria de migração de credenciais/database PostgreSQL, mudanças desses campos em runtime persistente são bloqueadas com `persistent_database_environment_change_requires_migration`. Isso é gate de integridade, não ausência da variável no estágio.

## Preview Compose vinculado

O Agenda P1020 expôs a divergência histórica: o W1 real recebia secrets/interpoladores por env privado enquanto o controller de Preview estava vazio. O runtime W1 agora usa um override privado root-only:

`/srv/cloudif/preview-workspaces/p1020/runtime/w1-environment.override.yaml`

Esse arquivo nunca entra em Git e nunca deve ser exibido. O deploy protegido do W1 usa o override junto ao Compose canônico e recria apenas API/Web quando necessário, preservando DB/volume.

## Secrets

Secrets seguem o mesmo lifecycle de estágio. O valor é resolvido somente em memória no caminho interno e nunca volta ao navegador/log/evidência. W→H e H→P promovem referências para o ambiente de destino em vez de reutilizar uma referência com escopo incorreto.

## Retenção e limpeza

- Preview: somente o slot fixo vigente deve permanecer ativo. Gerações legadas devem ser desligadas/retiradas de rota.
- Homologação: ao ser promovida, o mesmo deployment vira Produção; o bridge/rota H é removido. Homologação substituída e nunca promovida tem runtime removido, mantendo snapshot de auditoria/recuperação quando aplicável.
- Produção anterior: fica **parada**, não ativa, e preservada para rollback. Sua rota versionada antiga é removida do Publisher para não permanecer publicada por acidente.

## Estado validado no Agenda P1020

Na migração de 21/11/2026, controller e runtime foram comparados por hashes sem expor valores:

- Preview controller ↔ W1: 10/10 variáveis gerenciadas iguais;
- Production controller ↔ P6: 10/10 iguais;
- baseline de Homologação ↔ Preview: 10/10 iguais;
- aplicação inicial em W1/P6: `changedServices=[]`, sem recriação;
- Publisher: somente `1020-w1-preview` e `1020-p6-publication` permanecem;
- nenhum bridge de Homologação Agenda permanece ativo/residual;
- W3 legado foi desligado;
- H4 runtime foi removido, com snapshot preservado;
- P3/P2 permanecem parados somente como rollback histórico quando aplicável.

## Implementação/reconciliação

Enquanto as árvores canônicas dos componentes legados ainda não refletirem integralmente o runtime a9/compose, os deltas reproduzíveis desta unidade são:

- `compat/cloudiff-stage-environment-executor-reconfigure.patch`;
- `compat/cloudiff-stage-environment-komodo-w1.patch`;
- `compat/cloudiff-stage-environment-config-controller.patch`;
- `compat/cloudiff-stage-environment-portal-publications.patch`;
- `compat/cloudiff-stage-environment-web.patch`;
- `compat/cloudiff-stage-sensitive-web.patch`;
- `compat/cloudiff-stage-environment-reconcile-worker.patch`.

Não substituir componentes live por uma árvore presumidamente equivalente; reconciliar por base/proveniência e aplicar os deltas de forma verificável.

## Semântica da UI após promoção

Uma Homologação promovida deixa de ser ambiente ativo e passa a ser histórico. O Portal não deve oferecer Site, Terminal ou Variáveis da H publicada como se ainda existisse runtime H. Para Compose snapshot, uma H ativa exige estado `awaiting_homologation`/`homologated` e `sameInstancePromotionRequired=true`.

Projetos com Preview Forgejo/Komodo vinculado usam o W1 oficial como identidade do Preview. O overview não pode cair em um registro do Preview Broker legado quando a consulta ao Broker/Executor estiver temporariamente indisponível; nesse caso mantém a identidade/URL W1 com estado de atenção.

## Builder seguro do W1 e assets públicos

No Agenda P1020, o sync protegido do Preview não usa diretamente `frontend/Dockerfile`; ele constrói a imagem Web com o builder privado `runtime/Dockerfile.web`. Portanto correções de permissões do `dist` precisam existir também nesse builder.

O builder protegido deve executar `chmod -R a+rX /app/dist` após `npm run build`. Sem isso, arquivos copiados de `frontend/public` podem chegar à imagem Nginx como `0600`: `index.html` e bundles continuam funcionando, mas logo, favicons, manifest e service worker retornam HTTP 403 para o usuário `nginx`.

Aceite mínimo do builder Web protegido: logo, ícones, `sw.js`, `manifest.webmanifest` e `/` respondem HTTP 200; arquivos públicos ficam legíveis pelo worker Nginx; DB do W1 permanece com a mesma identidade durante o redeploy.
