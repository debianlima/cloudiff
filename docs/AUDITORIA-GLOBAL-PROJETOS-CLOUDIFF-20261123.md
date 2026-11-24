# Auditoria global dos projetos CloudIFF — 23/11/2026

## Escopo

Consolidação final do inventário do Portal, números públicos reservados, runtime W/H/P, ferramentas PHP/Node/Terminal, read-model e resíduos de exclusão.

## Classificação canônica

A existência de uma linha em `project_public_ids` **não significa que o projeto ainda exista**. O número público é preservado após exclusão para impedir reutilização acidental e manter rastreabilidade.

Estados canônicos:

- `current`: existe linha em `projects`; pode possuir runtime, integração e ACL;
- `reserved-deleted`: não existe linha em `projects`; o número público permanece reservado e não autoriza provisionamento, Preview, Terminal, PHP/Node ou publicação;
- `draft-no-runtime`: projeto atual deliberadamente sem aplicação executável/Preview;
- `current-runtime`: projeto atual com Preview/integração operacional.

## Projetos atuais

| Nº | Projeto | Estado consolidado |
|---:|---|---|
| 1001 | laboratorio-de-hardware | current-runtime; W1/P14 padronizados |
| 1002 | silvipro | current-runtime; W1 e Produção legada P1 |
| 1020 | agenda-unica | current-runtime; W3 específico do projeto e Produção moderna |
| 1021 | cpuhub | current-runtime; W1 e Produção legada P5 |
| 1022 | cadales | current-runtime; W1 e Produção legada P2 |
| 1025 | paperclip | current-runtime; W1 composto; preflight H por snapshot integral app+volume |
| 1026 | sgrep-v2 | current-runtime source-linked W1; preflight H integral app+db+sat |
| 1027 | msha | draft; repositório sem `docker-compose.yml` de aplicação e sem Preview; tenant Supabase existente é camada separada |
| 1028 | pghd-contexto | draft-no-runtime; agregador/documentação, sem aplicação executável configurada |

## Números reservados de projetos excluídos

Os 16 registros abaixo não são projetos atuais e não devem ser “recuperados” apenas porque possuem número público:

| Nº | Slug |
|---:|---|
| 1003 | silvipro2 |
| 1004 | lima-teste |
| 1005 | teste-lima |
| 1006 | lima-teste-3 |
| 1007 | silvipro-jt-2026 |
| 1008 | teste |
| 1010 | teste-sofa |
| 1011 | tuleap-laboratorio-de-hardware |
| 1014 | grupix |
| 1015 | teste-4 |
| 1016 | teste-3 |
| 1017 | teste-5 |
| 1018 | testando123 |
| 1019 | hardness-e2e-0254 |
| 1023 | isha |
| 1024 | mvplanner |

A evidência histórica de exclusão em `/srv/cloudif/admin-project-deletions/` confirma que os projetos foram removidos deliberadamente e que o número público foi preservado.

## Resíduo encontrado e corrigido

Durante a auditoria, cinco projetos `reserved-deleted` possuíam Preview W1 residual criado posteriormente por rotina de recuperação antiga:

- 1007 `silvipro-jt-2026`;
- 1010 `teste-sofa`;
- 1019 `hardness-e2e-0254`;
- 1023 `isha`;
- 1024 `mvplanner`.

Esses containers não possuíam volume Docker próprio de aplicação; montavam checkouts históricos e arquivos de runtime de stage. Foram removidos pelo fluxo oficial de exclusão/reconciliação, preservando os números públicos. Antes da limpeza foram gerados `git bundle` restritos em backup, sem duplicar credenciais do `.git/config`.

Regra: **nunca recriar Preview de `reserved-deleted`**. Runtime recovery exige linha atual em `projects` e autorização correspondente.

## Correções permanentes

1. O read-model `projects/public-catalog` lista apenas projetos atuais (`project_public_ids JOIN projects`).
2. Reservas ficam em `projects/reserved-public-numbers` com `lifecycle=reserved-deleted`.
3. A auditoria noturna compara o catálogo apenas com projetos atuais.
4. A auditoria registra `reserved-deleted-operational-residue` quando uma reserva reaparece em tabelas operacionais.
5. A auditoria consulta em modo somente leitura o status de Preview para reservas e registra `reserved-deleted-preview-runtime` se surgir runtime residual.
6. `/unpublish` deve remover Produção/aliases **e todos os stages W/H/P** ligados ao mesmo `public_number`, preservando certificados para auditoria/rollback.
7. `ensure_preview`/`recreate_preview`/status de provisionamento continuam exigindo linha atual em `projects`; número reservado isolado nunca autoriza mutação.

## MSHA

O MSHA é projeto atual, mas não possui aplicação pronta para W1. O repositório contém apenas documentação inicial e o stack Komodo declara `docker-compose.yml` ausente. Portanto não foi criado Preview artificial.

O tenant Supabase `iff3546365-msha` é independente da aplicação. A reconciliação de 23/11/2026 completou os serviços previstos do tenant existente: DB, Auth, Studio, Kong, Meta, Realtime, Storage e Supavisor ficaram saudáveis; Functions ficou running. Nenhum volume foi apagado e o banco não foi resetado. Essa camada permanece separada do lifecycle W/H/P da aplicação.

## PGHD Contexto

`pghd-contexto` é deliberadamente `draft-no-runtime`. Não deve receber W/H/P até que exista repositório/aplicação declarada por contrato.

## Regra operacional para agentes

Antes de qualquer recuperação/provisionamento:

```text
project_public_ids existe?
       ↓
projects existe?
  não → reserved-deleted → NÃO provisionar
  sim → validar owner/ACL/integração → operar o estágio real
```

Nunca usar `project_public_ids` como catálogo de projetos ativos.

## Referências

- `docs/PADRAO-CLOUDIFF-FERRAMENTAS-RUNTIME-ESTAGIO-20261123.md`
- `docs/PADRAO-CLOUDIFF-INDICE-READMODEL-PORTAL-20261122.md`
- `docs/RUNBOOK-PADRAO-CLOUDIFF-WHP-CONTINUIDADE.md`
- `docs/AUDITORIA-GLOBAL-PROJETOS-WHP-20261122.md`

## Homologação pelo runtime real do Preview — 23/11/2026

O botão **Enviar Preview para homologação** usa a mesma identidade de runtime já adotada por PHP/Node/Terminal. Não existe mais fallback para o snapshot legado de `project_preview_state` quando o Preview vivo é genérico/source-linked/composto.

Rotas atuais:

- LabHardware W1 e Agenda W3: `linked-compose` existente;
- SilviPro W1, CPUHub W1 e Cadales W1: `preview-runtime` do container genérico real;
- Paperclip W1: `preview-runtime` do app real + volume persistente; a bridge pública é infraestrutura e é recriada para H;
- SGREP v2 W1: snapshot completo `app + db + sat`, incluindo volume do banco, binds autorizados e aliases internos `preview-db`/`preview-sat`;
- MSHA: `draft/source-incomplete`, sem aplicação para homologar;
- PGHD Contexto: `draft-no-runtime` por contrato.

O Executor aceita `cloudif-p<NUM>-preview-web` somente como identidade genérica **W1 exata**, valida labels/projeto/stage/Git e nunca aceita nome livre. Source-linked descobre companheiros somente pelo prefixo/labels do mesmo projeto e restringe binds a checkout, stage-runtime ou `/srv/cloudif/<slug>`.

A restauração H preserva aliases internos de rede, mounts, rootfs e ambiente privado root-only. A bridge pública Wn não entra no snapshot; H recebe sua própria bridge/URL.

Pré-flight live sem criar candidato: 7 projetos publicáveis `ready`; ambientes de Homologação válidos e sem variável obrigatória faltante. Auditoria noturna: 9 projetos atuais, 16 reservas excluídas, 0 issues, nenhuma mutação. Evidência: `docs/audits/homologation/20261123-preflight-summary.json`.

## Fechamento global dos projetos — 23/11/2026

Estado atual comprovado:

- **9 projetos atuais** no catálogo canônico e **16 números públicos reservados** de projetos excluídos;
- auditoria noturna: `issue_count=0`;
- 7 projetos com Preview operacional: todos `healthy=true`, PHP/Node coerentes, Terminal pronto e `canSubmitHomologation=true`;
- 6 Produções ativas: PHP/Node/Terminal coerentes com a identidade real do estágio;
- CPUHub P2/P3 históricas realmente Offline;
- nenhuma H rejeitada mantém container em execução; snapshots antigos remanescentes foram aposentados;
- nenhum projeto `reserved-deleted` mantém container ou rota W/H/P;
- MSHA: tenant Supabase pronto; aplicação permanece `source-incomplete`, sem fabricar W1;
- PGHD Contexto: `draft-no-runtime` deliberado.

O publisher v2 live foi promovido por canary para a release `20261123T000042Z-v18-npm-publisher-reserved-stage-cleanup-f6cc6860`, que remove stages W/H/P no `/unpublish`. O Nginx foi validado antes/depois.

A janela de Publicações passou a buscar `release-flow` com `cache: no-store`; o asset live é `publication-release.js?v=20261123-release-nostore-v13`. Isso impede que uma falha antiga continue aparecendo depois de uma operação H mais recente bem-sucedida/rejeitada.

O servidor Komodo `Local` apresentava drift de confiança com o Periphery, bloqueando criação de Terminal por container. A confiança foi reconciliada pela API oficial do Komodo, sem registrar ou exibir a chave. Depois da reconciliação, Terminal passou nos sete Previews e nas seis Produções ativas.

Agenda W3 e LabHardware W1 tiveram ainda um fallback de status local seguro: quando o inventário de serviços do Core vem vazio, o agente aceita apenas containers `running` cujo label `com.docker.compose.project` corresponda exatamente ao stack. Nenhuma identidade é inferida apenas por nome.

Evidência máquina-legível: `docs/audits/FINAL-PADRONIZACAO-PROJETOS-20261123.json`.
