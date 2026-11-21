# Agenda P1020 — fechamento do cutover H5 → P3

Após a promoção in-place de H5 para P3, o estado lógico do Portal já indicava P3 ativa, mas ficaram dois resíduos de runtime: o bridge/container legado P2 continuava `running` e o vhost H5 permanecia no Publisher apontando para um bridge já parado.

## Correções aplicadas

- `cloudif-p1020-p2-publication-web` foi **parado, não removido**, após comprovação de que P3, `1020.cloudiff.duckdns.org` e `agendaunica.cloudiff.duckdns.org` respondiam a revisão `e32213d0b4d2`.
- O bridge H5 `cloudif-p1020-d5-web` já estava parado; o deployment `dep_23d8e626b85daf7d91bdece4` permaneceu rodando e agora está `environment=production` — isto é intencional, pois é a própria instância promovida.
- Os dois server blocks de `1020-h5-homologation.cloudiff.duckdns.org` foram removidos do Nginx com backup, `nginx -t` PASS e reload.
- A chave `1020-h5-homologation` foi removida também do `state.json` do Publisher e o serviço live foi reiniciado para impedir que o vhost reapareça em renderizações futuras.
- A UI passou a representar candidato publicado como `H5 → P3 · Ciclo concluído / Promovida para Produção`, mantendo H5 apenas como histórico de auditoria.
- Foi adicionado fallback autenticado e fail-closed para desativar Produção legada na primeira migração ao modelo novo; ele valida nome e labels e somente executa `docker stop`, preservando recursos para rollback.

## Prova final

- P3 `/api/health`: HTTP 200, revisão `e32213d0b4d2`.
- `1020.cloudiff.duckdns.org/api/health`: HTTP 200, mesma revisão.
- `agendaunica.cloudiff.duckdns.org/api/health`: HTTP 200, mesma revisão.
- P2: container `exited`; URL P2 não serve mais a aplicação (502).
- H5 bridge: `exited`; vhost H5 específico removido do state/config do Publisher.
- P3 bridge: `running`.
- deployment promovido: `dep_23d8e626b85daf7d91bdece4`, `environment=production`, `status=running`.

## Limitação do Publisher live

A árvore fonte atual já possui `POST /stage/delete` e testes idempotentes para remoção de estágio, porém o binário live em Maurício ainda não expõe essa rota. Não foi substituído nesta unidade porque a procedência exata do binário v2 live continua não reconciliada. O cleanup H5 atual foi feito diretamente em state/config com backup e reload seguro. Em release futura do Publisher, usar `/stage/delete` no fluxo para tornar esse cleanup automático e auditável.
