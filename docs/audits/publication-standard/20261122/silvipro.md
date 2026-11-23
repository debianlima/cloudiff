# Auditoria CloudIFF — silvipro (1002)

Data: 22/11/2026. Classificação: **PARCIAL_PRODUCAO_LEGADA_PLACEHOLDER**.

## Referência obrigatória

- `docs/PADRAO-CLOUDIFF-PREVIEW-HOMOLOGACAO-PRODUCAO-20261120.md`
- `docs/RUNBOOK-PADRAO-CLOUDIFF-WHP-CONTINUIDADE.md`
- `docs/FLUXO-WHP-PUBLICACAO.md`
- `docs/AGENDA-P1020-PROCEDIMENTO-GERENCIAMENTO-PUBLICACOES.md`

## Estado observado

- Integração: `ready`; Forgejo `done_via_forja_agent`; Komodo `done_via_komodo_agent`; Supabase `done`.
- Preview: `W1`, URL `https://1002-w1-preview.cloudiff.duckdns.org/`, health do read-model `True`, runtime `generic-preview`.
- Homologação atual: nenhuma candidata ativa.
- Produção ativa: `P1`, URL `https://1002-p1-publication.cloudiff.duckdns.org/`, runtime online `True`, healthy `True`.
- Histórico operacional: 0 versão(ões) no read-model atual.
- Alias(es): `silvipro.cloudiff.duckdns.org`.

## Navegação real no readiness

- alias: `https://silvipro.cloudiff.duckdns.org/` → **silvipro · primeiros passos**.
- preview: `https://1002-w1-preview.cloudiff.duckdns.org/` → **silvipro · primeiros passos**.
- production: `https://1002-p1-publication.cloudiff.duckdns.org/` → **silvipro · primeiros passos**.
- stable: `https://1002.cloudiff.duckdns.org/` → **silvipro · primeiros passos**.

## Adequação necessária

Transporte W/P funciona, mas a aplicação ainda serve a página de primeiros passos. Corrigir código-fonte e migrar P1 legada no próximo ciclo H→P humano.

## Gates

- Não criar H/P automaticamente para resolver drift de catálogo ou conteúdo.
- Provar runtime real antes de mostrar Online/Offline.
- Preservar número/URL do Preview existente.
- Próxima Produção moderna deve promover a mesma instância homologada.
- Produção substituída só pode ser declarada Offline após prova `inactive|removed` no Executor.
- Registrar prestate, rollback, evidência e atualizar esta auditoria após remediação.

## Índice/read-model obrigatório — 22/11/2026

O caminho quente da interface é o SQLite `/var/lib/cloudif/portal/cloudif-portal-readmodel.db`; não varrer Docker/filesystem/Komodo para renderizar listas. Mutação em provisionamento, ambiente, W/H/P, histórico, rollback, exclusão, Conectores ou Aprovações deve invalidar/atualizar o índice no próprio fluxo e disparar refresh em background. Leitura usa stale-while-revalidate. O refresh global é rede de segurança a cada 5 minutos; a auditoria completa roda 03:20 `America/Sao_Paulo` e nunca muta runtime. Norma: `docs/PADRAO-CLOUDIFF-INDICE-READMODEL-PORTAL-20261122.md`.

## Ferramentas de runtime por estágio — 23/11/2026

Norma: `docs/PADRAO-CLOUDIFF-FERRAMENTAS-RUNTIME-ESTAGIO-20261123.md`.

PHP, Node.js e Terminal devem resolver o mesmo `project + stageCode + runtime identity` selecionado; não derivar `api/web/app` por convenção, não copiar Wn de outro projeto e não recriar URL/container para diagnóstico. Preview linked-compose usa stack real; H/P Compose usam `services/routes` do Executor; Preview composto usa par numerado app/web; P legada usa container versionado exato. Ausência de PHP/Node é `available=false`, não erro. Terminal nunca contorna ACL.
## Prova runtime tools — 23/11/2026

Preview genérico W1 e Produção legada P1 passaram PHP/Node/Terminal. O Terminal P1 usa o container versionado real e não altera a natureza legada da Produção.
