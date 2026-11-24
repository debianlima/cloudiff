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

## Ferramentas de runtime por estágio — 23/11/2026

Norma: `docs/PADRAO-CLOUDIFF-FERRAMENTAS-RUNTIME-ESTAGIO-20261123.md`.

PHP, Node.js e Terminal devem resolver o mesmo `project + stageCode + runtime identity` selecionado; não derivar `api/web/app` por convenção, não copiar Wn de outro projeto e não recriar URL/container para diagnóstico. Preview linked-compose usa stack real; H/P Compose usam `services/routes` do Executor; Preview composto usa par numerado app/web; P legada usa container versionado exato. Ausência de PHP/Node é `available=false`, não erro. Terminal nunca contorna ACL.
## Prova runtime tools — 23/11/2026

Agenda preserva Preview **W3** e Terminal resolve o serviço real `api`. W3 é identidade deste projeto, não default global. Produção P11 resolve o deployment real e Terminal `web`.

## Homologação pelo runtime real — 23/11/2026

Agenda continua no caminho linked-compose W3 próprio do projeto; W3 não é default global e nenhuma identidade foi alterada.

## Fechamento de padronização — 23/11/2026

Classificação atual: `current-runtime`. Estado: W3 / P11. A norma PHP/Node/Terminal, read-model e lifecycle W/H/P está referenciada em `docs/audits/FINAL-PADRONIZACAO-PROJETOS-20261123.json`.
