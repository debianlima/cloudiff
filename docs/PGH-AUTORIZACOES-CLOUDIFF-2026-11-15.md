# PGH / CloudIFF — autorizações condicionadas e acompanhamento

Protocolo: **PGH-AUT-20261115-001**. Registrado em 15/11/2026,
12:10 UTC, pela identidade documentacao/cloudiff/doc-01.

O solicitante declarou autoridade dentro dos recursos sob sua
responsabilidade e aprovou **13 pedidos condicionados**. O PGH
registrou e distribuiu os pedidos a agentes existentes, mas não
iniciou automaticamente sessões, não concedeu root, não alterou
ACLs, não rotacionou credenciais e não liberou deploy ou reboot.

**Fonte da verdade:** protocolo em arquivos restritos no controlador
PGH LabIFF (cloudiff-admin/evidencias/PGH-AUT-20261115-001.md
e .json), memórias append-only e evidências de cada agente.
O Atlas é uma projeção sanitizada para humanos, não um sistema de
liberação ou um monitor de saúde em tempo real.

## Matriz de responsáveis e condições

| Pedido | Agente | Tarefas PGH | Condição de execução |
| --- | --- | --- | --- |
| G0 — Delegação de autoridade | infra-01 | T-003, T-004 | Confirmar titularidade, escopo, privilégios mínimos e lock |
| G1 — Backup e restauração | infra-01 | T-004 | Conferir cópias e teste isolado de restore/rollback |
| G2 — OpenBao e secret_ref | infra-01 | T-006, T-007, T-008 | Identidade, política ACL, TTL, revogação, auditoria e restauração |
| G3 — Komodo e Forgejo | dev-02 | T-004 | Clone/fetch com broker em sandbox descartável, sem token em URL/config |
| G4 — Conter e rotacionar Git | infra-01 | T-003, T-004 | G0 a G3 comprovados, owner, continuidade e rollback |
| G5 — Reauditoria independente | aud-01 | T-008, T-003 | Após G4, confirmar zero exposições e ausência de regressão |
| F1 — Preview contínuo | dev-02 | T-004, T-007 | W1 ligado ao Forgejo e Hn independente; retirar abas legadas somente após migração testada |
| F2 — Hn para Pn | dev-01 | T-003 | Promover a mesma instância, variáveis corretas e rollback validado |
| F3 — ACL e jobs | dev-01 | T-002, T-010 | Revalidar autorização em fila e isolar tenants |
| F4 — Paperclip e previews | dev-02 | T-013 | Diagnóstico comprovado de SCM, owner, proxy, health e permissões |
| T1 — E2E autenticado | surface-01 | T-002, T-003, T-005 | Conta de teste em secret_ref e autorização de uso |
| R1 — GitHub e Atlas | dev-02 | T-004, T-005, T-007 | Revisão independente, CI, rollback e proteção contra main antiga |
| M1 — Atualizações de sistema | infra-01 | T-002, T-004 | Janela de manutenção, restore e autorização antes de reboot |

Os vínculos acima apontam tarefas existentes. Nenhuma tarefa foi
duplicada nem marcada concluída com base somente na autorização.

### Observações específicas

**G1:** o solicitante identificou servidor Samba de backup e
identidade para acesso. O destino e a identidade ficam em registro
operacional restrito; o endereço privado, o usuário e a senha não
são reproduzidos neste repositório nem enviados ao Atlas. Foi
confirmada apenas a conectividade TCP dos serviços SMB/SSH a partir
do LabIFF; login, compartilhamentos, cópias e restauração não
foram comprovados. Credenciais devem ser providas por canal seguro.

**F1:** não manter abas legadas da publicação. Adaptar o fluxo
a W1/Hn/Pn e retirar o legado somente após compatibilidade,
permissões, testes e rollback confirmados.

Nos outros pedidos, não houve observações adicionais além dos gates.

## Sequenciamento e critérios de aceite

1. G0 e G1 estabelecem autoridade e segurança de recuperação.
2. G2 exige cofre produtivo e secret_ref governado.
3. G3 comprova, em sandbox, operações Git sem credenciais embutidas.
4. G4 executa contenção e rotação somente com owners e plano
   aprovados. G5 reaudita independentemente.
5. F1/F2/F3/F4 não dispensam esses gates. O contrato de publicação
   exige Preview fixo, Homologação isolada e promoção da mesma
   instância aprovada com rollback e variáveis efetivas.
6. T1 somente com identidade de teste autorizada pelo cofre.
7. R1 não realiza merge ou deploy só porque o CI está verde;
   M1 não autoriza reboot automático.

## Código, PRs e riscos da release

Estado consultado em 15/11/2026 por doc-01:

- PR #35: https://github.com/debianlima/cloudiff/pull/35
  revisão 0faff71, CI verde, draft e sem merge.
- PR #37: https://github.com/debianlima/cloudiff/pull/37
  revisão b0264a1, CI verde, draft e sem merge.
- PR #38: https://github.com/debianlima/cloudiff/pull/38
  revisão 3a31fba, CI verde, draft e sem merge.
  Persistem verificações de transição transacional, rollback
  após alias/stop, variáveis efetivas e Docker real.
- PR #39: https://github.com/debianlima/cloudiff/pull/39
  revisão 75a6b4a, CI verde, draft e sem merge.
  Persistem riscos de atualização de papéis e corrida de ACL.

**Incidente P0 ainda aberto:** a auditoria reportou 22
configurações Git com credenciais expostas. Sem reauditoria
final, restauração comprovada, rotação autorizada e cofre
produtivo não é permitido declarar o incidente resolvido.

## Acompanhamento humano

- Atlas: https://atlas.limaeducation.duckdns.org/acompanhamento?project=cloudiff.project.platform&tab=visao
- Tarefas PGH: https://atlas.limaeducation.duckdns.org/acompanhamento?project=cloudiff.project.platform&tab=tarefas
- A projeção de CloudIFF inclui eventos e Markdown sanitizados,
  cujo horário de coleta deve ser conferido; não é streaming.
- Só CloudIFF e Dotfiles dispõem de feeds PGH vinculados
  individualmente. Os demais tenants possuem fichas sem
  atribuição artificial de tarefas ou memórias.
- Os agentes devem registrar evidência por ID de pedido e atualizar
  handoffs na memória canônica antes de declarar qualquer gate feito.

**Autorização condicionada não é certificado de conclusão.**

## Atualização operacional — 15/11/2026, 16h UTC

Os estados a seguir substituem apenas os valores temporais acima,
não alteram o caráter **condicionado** das autorizações.

| Fonte | Código revisado | CI | Publicação |
| --- | --- | --- | --- |
| CloudIFF PR #35 (documentação) | 7957edb | sucesso | draft, sem merge |
| CloudIFF PR #37 (catálogos/CI) | b0264a1 | sucesso | draft, sem merge |
| CloudIFF PR #38 (Hn/Pn) | 361d94d | sucesso | draft, sem deploy |
| CloudIFF PR #39 (ACL de jobs) | 75a6b4a | sucesso | draft, sem deploy |

- **F2:** o PR #38 corrigiu falhas sintéticas de transação
  SQLite e recuperação de alias/container após parada; o CI
  validou o código, mas ainda faltam Docker real descartável,
  tratamento de crash/journal e demonstração efetiva do mesmo
  container Hn/Pn com variáveis Pn. Não marcar F2 como aprovado.
- **F3:** o PR #39 contém revalidação de ACL antes da operação
  enfileirada; ainda dependem de revisão os papéis privilegiados
  e a janela de corrida entre verificação e aplicação.
- **F4/F1:** a última auditoria registrou quatro previews W1
  respondendo 502, Paperclip com 403 ainda não classificado como
  falha sem autenticação e SilviPro com incompatibilidade de
  hostname TLS/SNI. A correção de certificado depende do
  responsável, evidência e rollback; não contornar TLS.
- **G1:** a infraestrutura testou a integridade e restauração
  em tmp de um backup **do próprio PGH**, mas isso não substitui
  teste de restauração de backups produtivos do CloudIFF/Samba.
- **G4:** o incidente P0 de 22 configurações Git com
  credenciais expostas ainda exige contenção, substituição,
  revogação e reauditoria sob autorização efetiva.
- **R1:** o Atlas possui candidato de integração interno
  3938944 na branch de review de dev-02, partindo do commit
  de assets publicados 357f762. Uma revisão independente
  de doc-01 comprovou paridade dos arquivos, testes offline
  de inventário/segurança e teste de acessibilidade das
  nove abas em 1365/390/320 px. O teste adicional de busca
  de eventos terminou inconclusivo por timeout do Chromium.
  Sem aceite de Surface em navegador autenticado, sem
  aprovação da infraestrutura e da auditoria, **não**
  executar merge de main nem novo deploy.
- **Atlas PGH:** snapshots são importados manualmente com
  integridade, backup e autenticação; o painel pode se tornar
  defasado. Não interpretar o número de eventos como
  relatório em tempo real e não atribuir journals da
  plataforma aos tenants sem vínculo explícito.

A memória PGH e os registros restritos permanecem a fonte
canônica de estado de tarefas e de incidentes. Antes de
qualquer decisão operacional, o agente deve reler os gates
G0–G5 na memória e obter aprovação concreta do titular.
## Reauditoria — 15/11/2026, 17h30 UTC

Esta atualização indica o estado **observado**, não libera
automaticamente nenhuma das 13 autorizações condicionadas.

### F2 — Código PR #38 versus produção

- HEAD revisto: [PR #38](https://github.com/debianlima/cloudiff/pull/38)
  revisão 42774c3 (draft, não mesclado), CI concluído com sucesso.
- Aud-01 validou 19/19 testes do contrato sintético e
  10/10 testes próprios da compensação de alias da primeira Pn.
  O candidato retira a associação pública do container candidato
  quando a primeira promoção falha após operação de banco.
- **Não há prova de conclusão Hn→Pn:** execução real com Docker
  descartável autorizado, preservação de rede/IP/aliases,
  variáveis efetivas de Pn, recuperação após crash e journal
  transacional continuam pendentes. A Forja ainda opera código
  anterior ao PR #38.
- PR #39 permanece draft sem deploy. ACL de jobs ainda exige
  verificar papéis privilegiados, revogação e janela TOCTOU.

### F1/F4/T1 — Disponibilidade e navegação

- Nova ocorrência T020 / MVPlanner: Preview W1 anteriormente
  HTTP 200 com tela de primeiros passos passou a responder
  **HTTP 502** em testes do Surface via browser e duas redes.
  O 200 anterior não era aceite da aplicação funcional.
- Surface observou **5 de 7 URLs W1 públicas com HTTP 502**
  (Agenda Única, Cadales, CPUHub, Laboratório de Hardware,
  MVPlanner). Paperclip retornou HTTP 403 anônimo; verificar
  autenticação/ACL antes de concluir falha funcional.
  SilviPro apresentou incompatibilidade TLS/SNI de hostname;
  não contornar verificação de certificado.
- Diagnóstico depende de owner, proxy/Komodo sanitizados,
  processo/upstream e análise de alterações recentes;
  nenhuma autorização de restart automático.

### R1 — Acessibilidade e candidata Atlas

- Surface reproduziu **9/9** perdas de foco ao navegar por
  cartões de subprojetos no Atlas em 1365, 390 e 320 px.
  O candidato isolado T019 transfere o foco ao H1 de destino
  após renderização; testes sintéticos 9/9 e regressão
  passaram na etapa anterior; a publicação foi verificada às 17h34 UTC.
- Separadamente, doc-01 corrigiu o seletor de teste de
  Markdown desatualizado (role button → role tab), commit
  de revisão no Git interno Atlas eb6fdcc, validado em
  1365 e 390 px sem alterar runtime/main.
- Candidata Atlas 3938944 permanece sob revisão e main
  histórica é ancestral da versão implantada. Dev-02 deve
  revisar ambas correções e solicitar aceite autorizado.
- Só dois projetos têm feed PGH explícito (CloudIFF e
  Dotfiles); os outros 22 não recebem memória inventada.
  Snapshot ainda é manual e sujeito a atraso.

### G0–G5 — Segurança e recuperação

- Auditoria independente confirmou persistência de **22
  origens Git com credenciais expostas**. G4 depende de
  contenção/rotação autorizadas; G5 exige reauditoria.
- G1 segue pendente: restauração de backup da memória PGH
  em temporário não comprova restauração produtiva do CloudIFF.
- OpenBao produtivo, identidades e ACL/TTL auditáveis e
  conta de teste via secret_ref continuam pendentes.
- Agenda Única API e Supabase Pooler de produção seguem
  em ciclo de reinícios, exigindo diagnóstico e rollback.
- Release CloudIFF v145.1 continua bloqueada mesmo com CI verde.


## Aceite técnico de T019 — 15/11/2026, 17h35 UTC

Este registro substitui o estado anterior de T019 como apenas
proposto. Não altera o estado dos demais gates de segurança.

- O dev-02 versionou a alteração de foco na branch interna
  Atlas fix/dev02-atlas-t019-focus-card-navigation-20261115,
  commit c41dd2d, com backup da versão JavaScript anterior.
- O arquivo JS instalado e o arquivo HTTP servido coincidem
  byte a byte com a branch de fix, SHA256
  b9740c807aa90964111bebea3086225e2381650dfcdbcef942c2bbaf732ef239.
- Auditoria read-only de doc-01: 3/3 assets frontend e
  3/3 backend alinham com essa revisão, saúde HTTP200 e
  acesso anônimo externo HTTP401. Somente o alerta
  MAIN_BEHIND_RELEASE continua ativo (a main ainda não
  contém essa correção).
- Teste Playwright independente doc-01, com os mesmos bytes
  do JS publicado e fixture sintética: **9/9 casos PASS**
  em 1365, 390 e 320 px; navegação Abrir projeto,
  Arquivos .md e controles transversais move foco ao H1
  correto, preserva URL/aba e não gera exceção JavaScript.
- **Estado T019**: correção publicada e conferida
  sinteticamente, aguardando aceite externo autenticado
  de Surface quando existir secret_ref homologado.
- **Estado T020**: a regressão HTTP502 do MVPlanner
  continua pendente de diagnóstico e correção; não foi
  afetada pela mudança de JS do Atlas.
- Esta publicação não libera W1/Hn/Pn do CloudIFF,
  G0–G5 nem merge de main Atlas.

## PR #40 — journal durável ainda não integrado

Atualização documental de 15/11/2026, aproximadamente 17h40 UTC.

- Dev-01 abriu [PR #40](https://github.com/debianlima/cloudiff/pull/40)
  head d6b82b1, base PR #38, draft/unmerged e CI remoto
  concluído com sucesso. A suíte completa local do módulo
  e repositório registrou 1378/1378 testes, incluindo
  14 testes do journal SQLite.
- O código adiciona protótipo independente de journal
  persistente para a publicação, mas **ainda não é usado
  pelos handlers de execução**. Sua presença não implementa
  recuperação automática após crash, isolamento real entre
  controladores nem autorização para promoção Docker.
- Aud-01 reproduziu uma questão de unicidade entre projetos
  com número público de publicação compartilhado e observou
  que uma referência SHA256 de evidência pode ser aceita
  sem prova autenticada no estado terminal. O integrador
  deverá vincular public_number às restrições reais do
  Portal, exigir identidade, fonte e verificador de
  evidência confiáveis e impedir reconciliação arbitrária.
- Antes de integrar PR #40: revisão independente de aud-01
  e infra-01, integração do journal no fluxo PR #38,
  lease e fencing de todos os controladores, teste
  descartável com falhas/crash, prova de recuperação
  do estado Docker/SQLite e cobertura dos gates G0–G5.
- Não converter CI verde, testes sintéticos ou permissão
  condicionada em autorização de deploy. A versão v145.1
  permanece bloqueada.
