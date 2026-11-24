# Auditoria CloudIFF — laboratorio-de-hardware (1001)

Data: 22/11/2026. Classificação: **PARCIAL_PRODUCAO_LEGADA**.

## Referência obrigatória

- `docs/PADRAO-CLOUDIFF-PREVIEW-HOMOLOGACAO-PRODUCAO-20261120.md`
- `docs/RUNBOOK-PADRAO-CLOUDIFF-WHP-CONTINUIDADE.md`
- `docs/FLUXO-WHP-PUBLICACAO.md`
- `docs/AGENDA-P1020-PROCEDIMENTO-GERENCIAMENTO-PUBLICACOES.md`

## Estado observado

- Integração: `ready`; Forgejo `done_via_forja_agent`; Komodo `done_via_komodo_agent`; Supabase `done`.
- Preview: `W1`, URL `https://1001-w1-preview.cloudiff.duckdns.org/`, health do read-model `True`, runtime `linked-compose`.
- Homologação atual: nenhuma candidata ativa.
- Produção ativa: `P12`, URL `https://1001-p12-publication.cloudiff.duckdns.org/`, runtime online `True`, healthy `True`.
- Histórico operacional: 1 versão(ões) no read-model atual.
- Alias(es): `labhard.cloudiff.duckdns.org`.

## Navegação real no readiness

- alias: `https://labhard.cloudiff.duckdns.org/` → **Login - Lab Hardware**.
- preview: `https://1001-w1-preview.cloudiff.duckdns.org/` → **Login - Lab Hardware**.
- production: `https://1001-p12-publication.cloudiff.duckdns.org/` → **Login - Lab Hardware**.
- stable: `https://1001.cloudiff.duckdns.org/` → **Login - Lab Hardware**.

## Adequação necessária

Preview e Produção estão saudáveis. No próximo release humano, criar H a partir do W fixo e promover a mesma H; depois deixar P12 histórica Offline.

## Gates

- Não criar H/P automaticamente para resolver drift de catálogo ou conteúdo.
- Provar runtime real antes de mostrar Online/Offline.
- Preservar número/URL do Preview existente.
- Próxima Produção moderna deve promover a mesma instância homologada.
- Produção substituída só pode ser declarada Offline após prova `inactive|removed` no Executor.
- Registrar prestate, rollback, evidência e atualizar esta auditoria após remediação.
## Remediação executada nesta auditoria

- Deployment órfão `dep_2d71aab93ec5c6ac95b92193` não tinha referência no Portal e mantinha apenas MySQL ligado.
- Foi desativado pelo Executor; status final `inactive`, app/db `Exited`, memória do DB `0B`.
- Snapshot/volumes foram preservados; Produção P12 permaneceu intacta.

## Índice/read-model obrigatório — 22/11/2026

O caminho quente da interface é o SQLite `/var/lib/cloudif/portal/cloudif-portal-readmodel.db`; não varrer Docker/filesystem/Komodo para renderizar listas. Mutação em provisionamento, ambiente, W/H/P, histórico, rollback, exclusão, Conectores ou Aprovações deve invalidar/atualizar o índice no próprio fluxo e disparar refresh em background. Leitura usa stale-while-revalidate. O refresh global é rede de segurança a cada 5 minutos; a auditoria completa roda 03:20 `America/Sao_Paulo` e nunca muta runtime. Norma: `docs/PADRAO-CLOUDIFF-INDICE-READMODEL-PORTAL-20261122.md`.

## Ferramentas de runtime por estágio — 23/11/2026

Norma: `docs/PADRAO-CLOUDIFF-FERRAMENTAS-RUNTIME-ESTAGIO-20261123.md`.

PHP, Node.js e Terminal devem resolver o mesmo `project + stageCode + runtime identity` selecionado; não derivar `api/web/app` por convenção, não copiar Wn de outro projeto e não recriar URL/container para diagnóstico. Preview linked-compose usa stack real; H/P Compose usam `services/routes` do Executor; Preview composto usa par numerado app/web; P legada usa container versionado exato. Ausência de PHP/Node é `available=false`, não erro. Terminal nunca contorna ACL.
## Prova runtime tools — 23/11/2026

W1/P14: PHP e Terminal resolvem `app`; Node ausente é exibido sem erro. IDs de `lab_hardware_app`, `lab_hardware_db`, bridge W1, app/db do deployment P14 e bridge P14 permaneceram idênticos antes/depois da correção. URLs W1/P14/stable preservadas.

## Homologação pelo runtime real — 23/11/2026

LabHardware continua no caminho linked-compose W1 já validado; não houve recriação ou alteração de URL/container nesta auditoria.

## Fechamento de padronização — 23/11/2026

Classificação atual: `current-runtime`. Estado: W1 / P15. A norma PHP/Node/Terminal, read-model e lifecycle W/H/P está referenciada em `docs/audits/FINAL-PADRONIZACAO-PROJETOS-20261123.json`.
