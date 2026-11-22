# Agenda P1020 — prova final do padrão W3/H/P e Portal

## Estado validado

- Preview fixo: W3.
- Produção ativa: P7.
- Endereço principal: alias `agendaunica.cloudiff.duckdns.org`.
- P2/P3/P6: históricas e Offline no encerramento.
- P7 e alias principal: revisão `18416127cdf9`.

## Variáveis

`envSave()` fecha o modal somente depois de `human/save` confirmar controller + runtime, emite `cloudif:environment-config-applied` e recarrega o ambiente externo. Asset do fluxo de publicação recebe cache-bust `20261122-final-pattern-v6`.

## Diagnóstico

W3 resolve `cloudif-agenda-unica-api-1` e `cloudif-agenda-unica-web-1`. P7 resolve `cloudif-dep-19bc037d073bf2418f9050c7-api/web`.

PHP e Node.js não estão instalados nesses runtimes; o diagnóstico devolve `ok=true`, `available=false` e mostra Python 3.14 na API. Isso substitui o falso erro/`package.json não encontrado` em container genérico.

## Histórico e exclusão

P6 foi usada como prova:

1. snapshot `snap_53f1ca2c4c72026e6ba676a9`, digest `d8e1413b...`, `status=ready`;
2. `Excluir container`: 3 containers + 1 volume runtime removidos; deployment antigo → `removed`; snapshot permaneceu `ready`; P6 → HTTP 202; alias principal permaneceu P7;
3. reidratação: novo deployment `dep_6523ed2707f3599af86d4c50`, mesmo snapshot/digest, H técnica → promoção da mesma instância para production, `stableRouteChanged=false`;
4. `Subir`: P6 HTTP 200 revisão `e32213d0b4d2`, enquanto alias/P7 continuaram `18416127cdf9`;
5. `Desligar`: P6 voltou HTTP 202; runtime ficou `inactive`, `canDelete=true`.

## Ativação principal

Chamada idempotente da P7 ativa retorna `stableUrl=https://agendaunica.cloudiff.duckdns.org/` e `numericStableUrl=https://1020.cloudiff.duckdns.org/`. O botão histórico é rotulado `Ativar em agendaunica.cloudiff.duckdns.org` quando o alias existe.

## Regressão

- 85 testes Portal: PASS.
- `git diff --check`: PASS.
- UI live/canônico: `cloudif-admin-portal-base.py` e `publication-release.js` com hashes idênticos no encerramento.
- Executor histórico: patch incremental reproduzível em `compat/cloudiff-historical-production-rehydrate-executor.patch`.

## Rollback operacional

Backups desta unidade:
- Portal: `/var/lib/cloudif/portal/backups/agenda-final-pattern-20261122T015540Z`;
- Komodo: `/srv/cloudif/backups/agenda-final-pattern-20261122T015540Z` e `/srv/cloudif/backups/komodo-historical-rehydrate-proxy-20261122T020350Z`;
- Executor: `/srv/cloudif/backups/executor-historical-rehydrate-20261122T020249Z`.

Não expor conteúdo de env/secrets nos artefatos de continuidade.
