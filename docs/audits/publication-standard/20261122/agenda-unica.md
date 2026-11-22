# Auditoria CloudIFF — agenda-unica (1020)

Data: 22/11/2026. Classificação: **CONFORME_REFERENCIA**.

## Referência obrigatória

- `docs/PADRAO-CLOUDIFF-PREVIEW-HOMOLOGACAO-PRODUCAO-20261120.md`
- `docs/RUNBOOK-PADRAO-CLOUDIFF-WHP-CONTINUIDADE.md`
- `docs/FLUXO-WHP-PUBLICACAO.md`
- `docs/AGENDA-P1020-PROCEDIMENTO-GERENCIAMENTO-PUBLICACOES.md`

## Estado observado

- Integração: `ready`; Forgejo `done_via_forja_agent`; Komodo `done_via_komodo_agent`; Supabase `done`.
- Preview: `W3`, URL `https://1020-w3-preview.cloudiff.duckdns.org/`, health do read-model `True`, runtime `linked-compose`.
- Homologação atual: nenhuma candidata ativa.
- Produção ativa: `P11`, URL `https://1020-p11-publication.cloudiff.duckdns.org/`, runtime online `True`, healthy `True`.
- Histórico operacional: 0 versão(ões) no read-model atual.
- Alias(es): `agendaunica.cloudiff.duckdns.org`.

## Navegação real no readiness

- alias: `https://agendaunica.cloudiff.duckdns.org/` → **Agenda Única**.
- preview: `https://1020-w3-preview.cloudiff.duckdns.org/` → **Agenda Única**.
- production: `https://1020-p11-publication.cloudiff.duckdns.org/` → **Agenda Única**.
- stable: `https://1020.cloudiff.duckdns.org/` → **Agenda Única**.

## Adequação necessária

Manter como projeto de regressão do padrão completo W3→Hn→mesma H em Pn; não normalizar o W3 histórico.

## Gates

- Não criar H/P automaticamente para resolver drift de catálogo ou conteúdo.
- Provar runtime real antes de mostrar Online/Offline.
- Preservar número/URL do Preview existente.
- Próxima Produção moderna deve promover a mesma instância homologada.
- Produção substituída só pode ser declarada Offline após prova `inactive|removed` no Executor.
- Registrar prestate, rollback, evidência e atualizar esta auditoria após remediação.

## Índice/read-model obrigatório — 22/11/2026

O caminho quente da interface é o SQLite `/var/lib/cloudif/portal/cloudif-portal-readmodel.db`; não varrer Docker/filesystem/Komodo para renderizar listas. Mutação em provisionamento, ambiente, W/H/P, histórico, rollback, exclusão, Conectores ou Aprovações deve invalidar/atualizar o índice no próprio fluxo e disparar refresh em background. Leitura usa stale-while-revalidate. O refresh global é rede de segurança a cada 5 minutos; a auditoria completa roda 03:20 `America/Sao_Paulo` e nunca muta runtime. Norma: `docs/PADRAO-CLOUDIFF-INDICE-READMODEL-PORTAL-20261122.md`.
