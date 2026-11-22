# Remediação — SGREP v2 P1026 — Preview source-linked no read-model

Data: 22/11/2026 UTC. Projeto: `sgrep-v2`, public number 1026.

## Estado encontrado

O Preview W1 já existia e estava funcional, mas `release_flow_status()` informava `configured=false`.

A infraestrutura real é source-linked/multicontainer:

- `cloudif-sgrep-v2-preview-app` — aplicação Node;
- `cloudif-sgrep-v2-preview-db` — PostgreSQL 16, volume `cloudif-sgrep-v2-preview-pgdata`;
- `cloudif-sgrep-v2-preview-sat` — toolchain/serviço auxiliar;
- `cloudif-p1026-w1-preview-web` — gateway Nginx público.

`project_preview_source_links` já registrava:

- stage W1;
- source commit `f29f752f2aadbdad46b46570b29b2895007fb6cb`;
- fonte Forgejo `cloudif-sgrep-v2/sgrep_v2`;
- bind da fonte readonly;
- dados isolados;
- HTTPS interno verificado;
- status `online`.

A URL pública W1 foi comprovada HTTP 200, inclusive `/login`.

## Causa do drift

`preview_status()` só reconhecia:

1. linked-compose;
2. preview multiservice gerenciado;
3. preview genérico do Komodo `project_preview_state`.

O contrato `project_preview_source_links` não era consultado, então um Preview existente e saudável desaparecia do painel.

## Correção de read-model

Foi adicionado `_source_link_preview_status()` ao Portal.

Quando multiservice/genérico não está configurado, o Portal consulta o source-link e, se a identidade for válida:

- preserva `stageCode=W1` e URL canônica;
- valida a URL externa com TLS/hostname;
- retorna `runtimeKind=source-linked-preview`;
- retorna `sourceMode=project-preview-source-link`;
- informa `sourceCommit`, repo e branch;
- usa `git.status=linked`, não `synced`, evitando afirmar uma sincronização automática que não existe;
- expõe `preview-app` + gateway como candidatos de diagnóstico.

O fallback é somente leitura; ele não cria, reinicia nem substitui containers.

## Diagnóstico PHP/Node

`runtime_diagnostic_target()` agora respeita a lista `containers` do Preview source-linked.

Prova SGREP:

- Node.js: `available=true`, container `cloudif-sgrep-v2-preview-app`, Node `v24.22.3`, npm `11.19.1`;
- PHP: `available=false`, com relatório dos runtimes realmente presentes;
- gateway Nginx não é confundido com aplicação.

## Verificação externa

Após a prova HTTP, `project_preview_source_links.public_external_verified` foi alterado de `0` para `1` com backup do Portal DB em:

`/var/lib/cloudif/portal/backups/sgrep-preview-source-link-20261122T030420Z`

## Limpeza de resíduos

Após backup de `docker inspect`, foram removidos apenas containers `exited` sem volume de dados ativo:

- `cloudif-sgrep-v2-preview-rollback-f29f752f2a-1795212450`;
- `cloudif-sgrep-v2-sat-image-test`;
- `cloudif-sgrep-v2-sat-smoke`;
- `cloudif-sgrep-v2-web-image-test`;
- `cloudif-sgrep-v2-web-smoke`.

Backup:

`/srv/cloudif/backups/sgrep-exited-residuals-20261122T030525Z`

Os quatro componentes ativos do Preview não foram alterados.

## Terminal

O Terminal do Preview source-linked ainda não possui endpoint explícito que selecione com segurança `preview-app`. O endpoint genérico de terminal audita a Stack do projeto e pode escolher runtime diferente; portanto não foi usado como fallback.

A validação via usuário de auditoria também foi corretamente bloqueada por ACL de escrita.

Próxima evolução necessária: criar/usar contrato de terminal source-linked que valide container `org.cloudiff.project=<slug>` + `org.cloudiff.stage=preview`, estado running e ACL do ator, sem redirecionar para a stack de homologação/produção.

## Estado final

- Portal: W1 `configured=true`, `healthy=true`;
- runtime kind: `source-linked-preview`;
- source commit: `f29f752f2aadbdad46b46570b29b2895007fb6cb`;
- W1 público: HTTP 200;
- Node/PHP stage-aware: funcional;
- projeto continua `draft`; nenhuma Produção foi criada ou alterada.
