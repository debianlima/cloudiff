# Agenda P1020 — correção do gateway de promoção H5 → P

A tentativa autenticada de publicação P3 chegou ao worker e ao Deployment Broker, mas o Broker recebeu HTTP 404 `not_found` ao chamar `/v1/compose-deployments/promote` através do gateway Komodo em `10.62.91.2:18098/cloudif/executor`.

O executor direto em `18230` já continha a rota. O defeito estava na allowlist do Komodo Agent, que ainda encaminhava apenas as rotas antigas.

## Correção

Foram liberadas no gateway, com timeout explícito:

- `POST /v1/compose-deployments/promote`;
- `POST /v1/deployments/deactivate`;
- `POST /v1/publication-bridges/deactivate`.

Testes sem efeito usando payload vazio confirmaram que as três chamadas chegam ao Executor e retornam seus erros de validação (`invalid_*_request`), em vez do `404 not_found` do gateway.

O registro idempotente da tentativa anterior foi removido somente após backup e validação estrita de que correspondia ao erro 404 do gateway. Isso permite uma nova tentativa sem replay da falha cacheada.
