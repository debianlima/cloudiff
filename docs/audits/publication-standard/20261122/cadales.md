# Auditoria CloudIFF — cadales (1022)

Data: 22/11/2026. Classificação: **PARCIAL_PRODUCAO_LEGADA_PLACEHOLDER**.

## Referência obrigatória

- `docs/PADRAO-CLOUDIFF-PREVIEW-HOMOLOGACAO-PRODUCAO-20261120.md`
- `docs/RUNBOOK-PADRAO-CLOUDIFF-WHP-CONTINUIDADE.md`
- `docs/FLUXO-WHP-PUBLICACAO.md`
- `docs/AGENDA-P1020-PROCEDIMENTO-GERENCIAMENTO-PUBLICACOES.md`

## Estado observado

- Integração: `ready`; Forgejo `done_via_forja_agent`; Komodo `done_via_komodo_agent`; Supabase `done`.
- Preview: `W1`, URL `https://1022-w1-preview.cloudiff.duckdns.org/`, health do read-model `True`, runtime `None`.
- Homologação atual: nenhuma candidata ativa.
- Produção ativa: `P2`, URL `https://1022-p2-publication.cloudiff.duckdns.org/`, runtime online `True`, healthy `True`.
- Histórico operacional: 0 versão(ões) no read-model atual.
- Alias(es): `cadales.cloudiff.duckdns.org`.

## Navegação real no readiness

- alias: `https://cadales.cloudiff.duckdns.org/` → **cadales · primeiros passos**.
- preview: `https://1022-w1-preview.cloudiff.duckdns.org/` → **cadales · primeiros passos**.
- production: `https://1022-p2-publication.cloudiff.duckdns.org/` → **cadales · primeiros passos**.
- stable: `https://1022.cloudiff.duckdns.org/` → **cadales · primeiros passos**.

## Adequação necessária

Transporte W/P funciona, mas a aplicação ainda serve a página de primeiros passos. Substituir o conteúdo no Forgejo e usar o próximo ciclo H→P same-instance.

## Gates

- Não criar H/P automaticamente para resolver drift de catálogo ou conteúdo.
- Provar runtime real antes de mostrar Online/Offline.
- Preservar número/URL do Preview existente.
- Próxima Produção moderna deve promover a mesma instância homologada.
- Produção substituída só pode ser declarada Offline após prova `inactive|removed` no Executor.
- Registrar prestate, rollback, evidência e atualizar esta auditoria após remediação.

## Índice/read-model obrigatório — 22/11/2026

O caminho quente da interface é o SQLite `/var/lib/cloudif/portal/cloudif-portal-readmodel.db`; não varrer Docker/filesystem/Komodo para renderizar listas. Mutação em provisionamento, ambiente, W/H/P, histórico, rollback, exclusão, Conectores ou Aprovações deve invalidar/atualizar o índice no próprio fluxo e disparar refresh em background. Leitura usa stale-while-revalidate. O refresh global é rede de segurança a cada 5 minutos; a auditoria completa roda 03:20 `America/Sao_Paulo` e nunca muta runtime. Norma: `docs/PADRAO-CLOUDIFF-INDICE-READMODEL-PORTAL-20261122.md`.
