# Agenda P1020 — H5 metadata reconciliation

A H5 (`1020-h5-homologation`) foi criada depois do rollout do executor/broker corrigidos, porém o Portal carregou `/srv/cloudif/lib/cloudif_portal_publications.py` antes da cópia do release porque `cloudif-admin-portal-base.py` insere `/srv/cloudif/lib` no início de `sys.path`.

Por isso, H5 foi criada corretamente no runtime, mas recebeu metadata do escritor antigo (`sameSnapshotAsProductionRequired`) e a UI a classificou como legada.

## Prova antes da reconciliação

- commit H5 = Preview W1 = `e32213d0b4d22fe5ff69241aaf5fdc33eb3f8d78`;
- deployment H5: `dep_23d8e626b85daf7d91bdece4`, `homologation/running`;
- snapshot: `snap_16b92e7065dbceb5c16dd8d5`;
- API, DB e Web H5: healthy;
- env dos três serviços: equivalente ao W1;
- artefatos API/Web comparados: equivalentes ao W1;
- banco lógico W1/H5: migração `1:initial`, 14 tabelas e `teacher_count=1`, todos iguais;
- H5 foi criada após o mtime do executor corrigido;
- promotion plan side-effect-free: `execution_allowed=true`, blockers `[]`, `sameDeploymentRequired=true`, `containerRecreationForbidden=true`.

## Correção

A biblioteca compartilhada recebeu somente os blocos H/P de promoção in-place já validados no release ativo. O registro H5 foi reconciliado sob backup e identidade exata, adicionando:

- `cloneMode=full-preview-runtime`;
- `sameInstancePromotionRequired=true`;
- `containersRecreatedForProduction=false`;
- `environment_revision=0` e `environment_digest=snapshotDigest`.

O painel, para o proprietário do projeto, passou a retornar `canPublish=true` e H5 compatível. Nenhuma publicação P foi executada nesta reconciliação.
