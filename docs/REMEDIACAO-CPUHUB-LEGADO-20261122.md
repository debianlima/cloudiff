# CPUHub P1021 — reconciliação do legado W/H/P

Data: 22/11/2026 UTC. Projeto: `cpuhub`, public number 1021.

## Estado final

- Preview contínuo W1 saudável: `1021-w1-preview.cloudiff.duckdns.org`.
- Git do Preview: `97af1e386fabb9b718f8aa100f200acfe6333264`, status `synced`.
- Produção ativa P5 saudável: `1021-p5-publication.cloudiff.duckdns.org`.
- Endereço numérico e alias `cpuhub.cloudiff.duckdns.org` continuam HTTP 200.
- P2 e P3 permanecem históricas Offline.
- H3 foi reconciliada de `awaiting_homologation` para `superseded` porque H4/P3 e H5/P5 posteriores já existiam.

## Limpeza aplicada

O Publisher possuía stages antigos W2, H2, H3, H4, H5, P2 e P3 mesmo com os respectivos runtimes inativos. Todos esses stages foram removidos. Restaram somente:

- `1021-w1-preview`;
- `1021-p5-publication`.

As URLs antigas agora caem no fallback do Portal (HTTP 302), em vez de responder 502 por upstream inexistente.

## Containers de Homologação legada

Os containers `cloudif-p1021-d2-web` até `cloudif-p1021-d5-web` foram removidos após prova de rollback:

- nenhum tinha volume Docker nomeado;
- apenas bind de `/run/cloudif/runtime.env`;
- todas as imagens continuavam presentes;
- os diretórios de Stack Komodo continuavam presentes.

`cloudif-p1021-d5-web` era duplicata da P5: mesma imagem/image-id, sem alias ativo. O alias `cloudif-p1021-active-web` pertence exclusivamente a `cloudif-p1021-p5-publication-web`.

Os registros legados `publication_runtimes` D1–D5 foram marcados `inactive/is_active=0` para impedir que terminal/ações futuras os tratem como Produção ativa.

## Histórico P2/P3

Os containers versionados P2/P3 continuam exited/preservados. O Portal mostra `runtimeState=offline` e `canStart=true`; portanto o humano ainda pode usar `Subir` para teste histórico sem afetar P5.

## Backups/rollback

- Portal: `/var/lib/cloudif/portal/backups/cpuhub-legacy-cleanup-20261122T031842Z`
- Forja: `/srv/cloudif/backups/cpuhub-legacy-cleanup-20261122T031842Z`
- Publisher/Nginx: `/opt/cloudiff-v2/backups/cpuhub-legacy-cleanup-20261122T031842Z`

O backup Forja contém `docker inspect` D2–D5, stacks e SQL de restauração de `publication_runtimes`. O backup Portal contém prestate/SQL de H3. Publisher/Nginx possuem prestate integral dos arquivos de roteamento.

## Lacuna restante

P5 é legado: H5/P5 não possuem prova do contrato `sameInstancePromotionRequired` e não devem ser reclassificadas retroativamente.

`assistente-interativo` não possui ACL do projeto. A migração final ao padrão deve ocorrer no próximo ciclo humano:

1. usuário trabalha no W1 atual;
2. envia W1 para nova H;
3. valida a H;
4. promove a própria instância H para nova P;
5. somente após health/cutover, P5 vira histórica Offline.
