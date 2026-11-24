# Auditoria CloudIFF — paperclip (1025)

Data: 22/11/2026. Classificação: **BLOQUEADO_RUNTIME_COMPOSTO_STABLE_502**.

## Referência obrigatória

- `docs/PADRAO-CLOUDIFF-PREVIEW-HOMOLOGACAO-PRODUCAO-20261120.md`
- `docs/RUNBOOK-PADRAO-CLOUDIFF-WHP-CONTINUIDADE.md`
- `docs/FLUXO-WHP-PUBLICACAO.md`
- `docs/AGENDA-P1020-PROCEDIMENTO-GERENCIAMENTO-PUBLICACOES.md`

## Estado observado

- Integração: `ready`; Forgejo `done_via_forja_agent`; Komodo `done_via_komodo_agent`; Supabase `done`.
- Preview: `W1`, URL `https://1025-w1-preview.cloudiff.duckdns.org/`, health do read-model `True`, runtime `None`.
- Homologação atual: nenhuma candidata ativa.
- Produção ativa moderna: nenhuma.
- Histórico operacional: 0 versão(ões) no read-model atual.

## Navegação real no readiness

- preview: `https://1025-w1-preview.cloudiff.duckdns.org/` → **Paperclip**.
- stable: `https://1025.cloudiff.duckdns.org/` → **502**.

## Adequação necessária

W1 real está saudável; endereço estável retorna 502 e existe D1 legado fora do modelo moderno. Preservar volume, definir manifest do runtime composto, reconciliar D1/stable e só então habilitar H→P.

## Gates

- Não criar H/P automaticamente para resolver drift de catálogo ou conteúdo.
- Provar runtime real antes de mostrar Online/Offline.
- Preservar número/URL do Preview existente.
- Próxima Produção moderna deve promover a mesma instância homologada.
- Produção substituída só pode ser declarada Offline após prova `inactive|removed` no Executor.
- Registrar prestate, rollback, evidência e atualizar esta auditoria após remediação.
## Conflito que impede limpeza automática

- `cloudif-p1025-d1-app`/`web` estão rodando e o app consome cerca de 1 GiB, com volume persistente preservado.
- Labels os identificam como `pgh-test` / `nonproduction-staged-build-v2`, mas o Publisher legado ainda declara `projects.1025.active_deploy=1` e `project_publications` mantém `d1` ativo.
- Essa divergência é result-determining: **não desligar nem remover D1 automaticamente** até o proprietário reconciliar se ele é canário ou Produção legada.
- O stable 1025 continua 502 e permanece P1 de remediação.

## Índice/read-model obrigatório — 22/11/2026

O caminho quente da interface é o SQLite `/var/lib/cloudif/portal/cloudif-portal-readmodel.db`; não varrer Docker/filesystem/Komodo para renderizar listas. Mutação em provisionamento, ambiente, W/H/P, histórico, rollback, exclusão, Conectores ou Aprovações deve invalidar/atualizar o índice no próprio fluxo e disparar refresh em background. Leitura usa stale-while-revalidate. O refresh global é rede de segurança a cada 5 minutos; a auditoria completa roda 03:20 `America/Sao_Paulo` e nunca muta runtime. Norma: `docs/PADRAO-CLOUDIFF-INDICE-READMODEL-PORTAL-20261122.md`.

## Ferramentas de runtime por estágio — 23/11/2026

Norma: `docs/PADRAO-CLOUDIFF-FERRAMENTAS-RUNTIME-ESTAGIO-20261123.md`.

PHP, Node.js e Terminal devem resolver o mesmo `project + stageCode + runtime identity` selecionado; não derivar `api/web/app` por convenção, não copiar Wn de outro projeto e não recriar URL/container para diagnóstico. Preview linked-compose usa stack real; H/P Compose usam `services/routes` do Executor; Preview composto usa par numerado app/web; P legada usa container versionado exato. Ausência de PHP/Node é `available=false`, não erro. Terminal nunca contorna ACL.
## Prova runtime tools — 23/11/2026

W1 composto: Node e Terminal agora usam `cloudif-p1025-w1-preview-app`; PHP ausente é exibido sem erro. O bloqueio de Homologação por manifest composto continua vigente; volume não foi alterado.

## Homologação pelo runtime real — 23/11/2026

Paperclip W1 passou no preflight `preview-runtime`: app real + volume persistente entram no snapshot; a bridge pública fica fora e será recriada em H. O bloqueio antigo de “manifest composto” foi substituído por este snapshot integral validado. Nenhuma H foi criada pela auditoria.

## Fechamento de padronização — 23/11/2026

Classificação atual: `current-runtime`. Estado: W1 / P1. A norma PHP/Node/Terminal, read-model e lifecycle W/H/P está referenciada em `docs/audits/FINAL-PADRONIZACAO-PROJETOS-20261123.json`.
