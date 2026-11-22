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
