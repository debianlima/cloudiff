# Agenda Única P1020 — conferências finais de Preview

Data: 22/11/2026.

## Terminal W3

O read-model já reconhecia o Preview W3 como `linked-compose`, com Stack Komodo `cloudif-agenda-unica`, mas `preview_terminal()` ainda caía no registro legado `project_preview_state`, cujo `stack_id` estava vazio. Isso produzia a mensagem “O Preview ainda precisa ser reconciliado para o runtime persistente”.

Correção:

- Portal detecta `linked-compose` e envia ao Komodo a identidade do Stack cadastrado;
- serviço permitido no Preview linked-compose da Agenda: `api`;
- Komodo valida `stack_id`, `stack_name`, projeto, serviço e container running;
- terminal criado/reutilizado: `cloudif-preview-api`;
- URL Komodo aponta para `stacks/<stack>/service/api/terminal/<terminal>`.

Prova live:

- HTTP 200;
- W3;
- Stack `6aac22340aa4149f0c38a686`;
- container `cloudif-agenda-unica-api-1`;
- serviço `api`;
- `target_mode=stack`;
- `terminalReady=true`.

## PHP e Node.js

O runtime real do W3 não contém PHP nem Node.js. A aplicação atual usa:

- API Python 3.14.x;
- frontend servido pelo container web;
- PostgreSQL 16.

O diagnóstico do Portal foi validado contra os containers reais `api` e `web`:

- PHP: `available=false`, HTTP 200;
- Node.js: `available=false`, HTTP 200;
- saída mostra explicitamente `php/node/npm=ausente` e detecta Python no container API.

Não instalar PHP/Node apenas para preencher a tela: as abas devem refletir o runtime real. O diagnóstico standalone também passou a respeitar o ambiente selecionado, igual ao modal.

## Administrador da Agenda

A conta ADMIN existente em W3 e P8 foi atualizada para as credenciais solicitadas pelo operador.

Medidas aplicadas:

- mesmo usuário ADMIN id 1 preservado;
- `setup_required=false`;
- `token_version` incrementado, invalidando sessões anteriores;
- TOTP permaneceu desativado, como já estava;
- senha processada somente em memória com `hash_password()`/scrypt da própria Agenda;
- nenhum valor de senha foi registrado em documentação, log ou backup;
- backup prévio contém somente metadados não sensíveis.

Provas:

- `verify_password()` retornou verdadeiro em W3 e P8;
- login HTTP real retornou 200 nos dois ambientes após aceite dos Termos;
- tipo da conta retornado: `ADMIN`;
- `setup_required=false`.

Backup não sensível:
`/srv/cloudif/backups/agenda-admin-reset-20261122T154611Z`.

## Saúde

- W3 `/api/health`: revisão `18416127cdf9`;
- P8 `/api/health`: revisão `18416127cdf9`;
- alias `agendaunica.cloudiff.duckdns.org`: revisão `18416127cdf9`.
