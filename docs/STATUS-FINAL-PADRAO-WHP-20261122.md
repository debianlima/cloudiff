# Status final — padrão CloudIFF W→H→P — 22/11/2026

Este arquivo é o ponto de entrada curto para continuidade operacional. Para detalhes, ler:

1. `docs/RUNBOOK-PADRAO-CLOUDIFF-WHP-CONTINUIDADE.md`;
2. `docs/AUDITORIA-GLOBAL-PROJETOS-WHP-20261122.md`;
3. o documento `REMEDIACAO-*` do projeto alvo.

## Matriz atual

| Projeto | Preview | Produção atual | Situação do contrato H→P | Próxima ação |
|---|---|---|---|---|
| Agenda Única (1020) | W3 saudável/synced | P8 + `agendaunica` | **Conforme same-instance H8→P8** | usar como referência/regressão |
| Cadales (1022) | W1 saudável/synced | P2 saudável | legado, sem prova same-instance | proprietário cria próxima H/P pelo fluxo atual |
| CPUHub (1021) | W1 saudável/synced | P5 saudável | legado, resíduos H limpos | proprietário cria próxima H/P pelo fluxo atual |
| Laboratório Hardware (1001) | W1 recuperado/synced | P12 + `labhard` | legado; H13/P12 eram deployments diferentes | proprietário cria nova H e promove a mesma instância |
| Paperclip (1025) | W1 saudável; app+gateway+volume | D1 legado | **bloqueado com segurança** até manifest composto | definir manifest/runtime completo antes de H |
| SGREP v2 (1026) | W1 source-linked saudável; Terminal validado no preview-app | nenhuma | Preview conforme; ainda sem Produção | publicar somente quando solicitado |
| SilviPro (1002) | W1 contínuo saudável/synced | P1 + `silvipro` | P1 importada como legado | proprietário cria próxima H/P same-instance |
| MSHA | não configurado | nenhuma | n/a | permanece draft |

## Invariantes que não podem regredir

- Wn é identidade fixa do Preview; recovery não cria novo slot.
- Forgejo atualiza o mesmo Wn.
- W→H congela runtime/código/variáveis aprovados.
- H→P promove a **mesma instância**, sem rebuild.
- H promovida não fica consumindo runtime residual.
- P históricas ficam Offline por padrão; `Subir` não troca alias principal.
- `Ativar no endereço principal` é a única ação de cutover.
- `Excluir container` nunca vale para a P ativa. Compose histórica preserva snapshot; legado inativo pode usar exclusão final validada e sem reidratação automática.
- Variáveis humanas são aplicadas diretamente ao estágio selecionado; secrets mascarados e rotacionáveis.
- PHP/Node/Terminal consultam o estágio real.
- Preview composto não pode usar snapshot genérico; exige manifest completo.
- Nunca “corrigir” legado mudando metadata para afirmar uma promoção que não ocorreu.

## Gates humanos ainda abertos

A identidade operacional `assistente-interativo` não possui ACL dos projetos Cadales, CPUHub, Laboratório, Paperclip e SilviPro para iniciar publicação em nome do proprietário. Isso é intencional. O agente pode preparar infraestrutura reversível e diagnosticar, mas não deve impersonar o usuário para criar H/P.

## Provas recentes

- Agenda: H8/P8 mesma instância; P2/P3/P6/P7 arquivadas e sem runtime físico.
- Laboratório: W1 recuperado; H11/H13/P5 residuais desligados; P12 preservada.
- Cadales: W1 sincronizado; W2/H2 antigos removidos; P2 preservada.
- CPUHub: W1 sincronizado; H3 superseded; D2–D5 e stages antigos limpos; P5 preservada.
- Paperclip: snapshot composto retorna 409 antes de qualquer efeito; W1/D1 preservados.
- SGREP: source-linked reconhecido/saudável e Terminal validado no `preview-app` com identidade estrita.
- SilviPro: W1/P1 separados e coerentes; conteúdo placeholder corresponde ao Git atual.

## Referências canônicas de continuidade

- Norma global: `docs/PADRAO-CLOUDIFF-PREVIEW-HOMOLOGACAO-PRODUCAO-20261120.md`.
- Operação/recuperação: `docs/RUNBOOK-PADRAO-CLOUDIFF-WHP-CONTINUIDADE.md`.
- Fluxo para usuários/agentes: `docs/FLUXO-WHP-PUBLICACAO.md`.
- Agenda P1020: `docs/AGENDA-P1020-PROCEDIMENTO-GERENCIAMENTO-PUBLICACOES.md`.

Essas referências prescrevem o comportamento atual. Documentos `REMEDIACAO-*` preservam evidência histórica e não substituem o procedimento vigente.
