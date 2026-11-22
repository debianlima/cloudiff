# SGREP v2 P1026 — Terminal do Preview source-linked

Data: 22/11/2026 UTC. Projeto: `sgrep-v2`, public number 1026.

## Problema

O W1 source-linked já era reconhecido pelo Portal, mas o Terminal do Preview continuava usando o contrato de Stack persistente (`project_preview_state`). SGREP não possui essa Stack como fonte de verdade do W1; a aplicação real está em `cloudif-sgrep-v2-preview-app`, registrada em `project_preview_source_links`.

## Contrato implementado

O Portal mantém ACL normal (`canWrite`) e lê do banco, sem aceitar container escolhido pelo navegador:

- `app_container` cadastrado;
- `source_commit` cadastrado;
- `stage_code` cadastrado.

O Komodo aceita o modo source-linked no endpoint existente `/komodo/project/preview/terminal` somente quando:

1. o container é exatamente `cloudif-<project>-preview-app`;
2. o container está running;
3. label `org.cloudiff.project` corresponde ao projeto;
4. label `org.cloudiff.stage=preview`;
5. label `org.cloudiff.source-commit` corresponde ao commit registrado.

Depois cria/reutiliza terminal Komodo com target `Container`. Não resolve Stack genérica e não aceita container arbitrário.

## Provas

Identidade correta:

- HTTP 200;
- container `cloudif-sgrep-v2-preview-app`;
- `stageCode=W1`;
- `target_mode=container`;
- `sourceLinked=true`;
- terminal `sh-cloudif-sgrep-v2-preview-app`;
- `secretValuesIncluded=false`.

Identidade adulterada usando o gateway público:

- HTTP 409;
- `source_linked_preview_identity_invalid`;
- nenhum redirecionamento silencioso para outro runtime.

W1 permaneceu saudável e continua redirecionando normalmente ao login da aplicação.

## Backups

- Portal: `/var/lib/cloudif/portal/backups/source-linked-terminal-20261122T032704Z`
- Komodo Agent: `/srv/cloudif/backups/source-linked-terminal-20261122T032704Z`
