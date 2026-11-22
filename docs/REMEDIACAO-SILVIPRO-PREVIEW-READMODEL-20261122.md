# Remediação — SilviPro P1002 — Preview e read-model

Data: 22/11/2026 UTC. Projeto: `silvipro`, public number 1002.

## Estado inicial

- Portal não reconhecia Preview configurado.
- W1/D2 antigos caíam no Portal ou em 502.
- Alias `silvipro.cloudiff.duckdns.org` e `1002.cloudiff.duckdns.org` exibiam `silvipro · primeiros passos`.
- Komodo Agent possuía uma base `r2` e uma P1 real registrada (`cloudif-p1002-p1-publication-web`) baseada em `cloudif/publication-p1002-d2:php8.3-node22`.
- O Forgejo/check-out canônico estava em `ad2273de08fac6189d19b2f8009b56157b0be594` e contém apenas o conteúdo inicial do projeto.

## Preview restaurado

Foi criado Preview pelo endpoint oficial `komodo/project/preview/recreate`, usando `source=production`, ator `assistente-interativo` e as variáveis do ambiente Preview carregadas apenas em memória.

O Komodo escolheu geração W2, preservando geração anterior. Estado final:

- container `cloudif-p1002-w2-preview-web`;
- `healthy=true`;
- source image id igual à P1 registrada;
- checkout Git sincronizado em `ad2273de08fac6189d19b2f8009b56157b0be594`;
- Publisher W2 ativo;
- `1002-w2-preview.cloudiff.duckdns.org` HTTP 200.

A rota W1 foi removida do estado do Publisher. O hostname W1 antigo pode responder 502 pelo proxy genérico, mas não possui stage nem bloco Nginx específico e não representa runtime ativo.

## Divergência de conteúdo

O Preview W2 monta o checkout Forgejo em `/var/www/html`; por isso serve `silvipro · primeiros passos`, que é o conteúdo atual do Git.

P1/D2 possuem conteúdo diferente dentro da imagem runtime (title `CloudIFF`) e não correspondem ao checkout Git atual. Portanto essas mudanças existem fora da fonte canônica e **não devem ser copiadas automaticamente para o Preview ou para o Forgejo** sem revisão humana.

Fingerprints de estrutura confirmam divergência entre W2 e P1.

## Correção global do read-model

SilviPro é classificado como `multi-service`. Antes, quando não havia Preview multiservice, `preview_status()` retornava imediatamente `configured=false`, ignorando um Preview genérico já existente no Komodo.

A regra foi corrigida:

1. se Preview multiservice está configurado, ele continua prioritário;
2. se multiservice não está configurado, o Portal consulta `/komodo/project/preview/status`;
3. se existir Preview genérico, ele é retornado como `runtimeKind=generic-preview`, `fallbackFrom=multiservice`.

Após a correção, `release_flow_status('silvipro')` reconhece W2 como `configured=true`, `healthy=true`.

## Produção

Nenhum cutover foi executado. O alias principal continua no D1 legado/placeholder.

A identidade real `assistente-interativo` não possui ACL de projeto no Portal. Portanto não foi tentada ativação da P1 nem criação de H/P por impersonação.

## Próxima ação humana necessária

O proprietário precisa decidir qual conteúdo é fonte correta:

- se o Forgejo `ad2273de...` está correto, W2 já representa a fonte canônica e o conteúdo runtime-only de P1/D2 é legado;
- se P1/D2 contém alterações que precisam ser preservadas, essas alterações devem ser revisadas e incorporadas ao Forgejo antes de uma nova Homologação.

Depois disso, usar o fluxo padrão W→H→P pelo Portal.
