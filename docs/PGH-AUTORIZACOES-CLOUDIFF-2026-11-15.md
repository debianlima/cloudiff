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

## Confirmação das 13 aprovações e revisão T021

Atualização de 15/11/2026, aproximadamente 18h UTC.

O solicitante confirmou expressamente: **todos os 13 pedidos estão
aprovados para prosseguimento dentro de seu escopo**. A confirmação
foi registrada como adendo restrito no PGH e despachada novamente a
infra-01 (G0/G1/G2/G4/M1), dev-02 (G3/F1/F4/R1),
dev-01 (F2/F3), aud-01 (G5) e surface-01 (T1).

O escopo permitido é verificar, preparar e executar ações
somente após os gates operacionais pertinentes. O aceite
administrativo **não certifica** privilégio de sistema,
titularidade de credencial de terceiro, backup restaurável,
cofre, teste de rollback ou resolução do incidente P0.
Nenhum pedido foi marcado concluído pela confirmação.

### G1 — Acesso seguro ao backup

Conectividade TCP ao servidor Samba de backup indicado
foi confirmada para SSH/SMB. A identidade atualmente
disponível no LabIFF não possui chave SSH do host
registrada e confiável; cliente SMB também não está
disponível nesta sessão. Acesso autenticado, integridade
dos arquivos e restauração isolada não foram validados.
Não foi desabilitada verificação SSH nem colocada
senha do solicitante em comandos, logs ou Git. A ação
depende de identidade e host key verificados pelo
responsável e secret_ref governado.

### R1 — T021: Voltar/Avançar no acompanhamento Atlas

Surface-01 identificou que navegar em cartões, abas
e arquivos Markdown com history.replaceState não
preservava o histórico do navegador. Doc-01 adaptou
a proposta do Surface sobre a correção T019 já
publicada, sem alteração do serviço ativo.

A proposta está em branch de revisão no Git Atlas interno:

- Branch review/doc01-atlas-t021-history-20261115,
  commit a9ff48e, baseado em c41dd2d (T019).
- Acrescenta tratamento popstate, pushState para
  alteração real de projeto/aba/documento, e mantém
  foco no H1 de contexto do projeto.
- Testes Playwright sintéticos: 2/2 projetos em
  desktop/mobile, 3/3 abas/documentos em diferentes
  resoluções, 9/9 casos de foco H1 preservado.
- Teste versionado de histórico cobriu 1365/390;
  320 px passou em execução isolada do mesmo código.
  Testes de hierarquia, documentos Markdown e
  importador sem segredos passaram.
- **T021 é candidato para revisão**, não está
  implantado. Dev-02 deve revisar e integrar em
  branch própria sob controle de concorrência;
  Surface deve validar a versão realmente servida
  antes de declarar o problema corrigido.

A versão Atlas main continua defasada e os bloqueios
CloudIFF de G0–G5, W1 e Docker Hn/Pn permanecem ativos.

## Revisão final — T021 publicado e importador estrito

Atualização de 15/11/2026, aproximadamente 18h05 UTC.

**T021 Atlas passou de revisão para publicado.**
O dev-02 publicou no Git interno Atlas a correção
fix/dev02-atlas-t021-browser-history-20261115,
commit 5b3c908. O arquivo JavaScript HTTP servido tem SHA256
eaf89f9b1a6e47b6a1b3923aae274dd5d1466274bfe642ad775c885c7bf4f20c,
idêntico ao Git da branch. Um backup da versão anterior
foi preservado antes da substituição.

- A auditoria doc-01 com a branch exata publicada confirmou
  3/3 assets de interface e 3/3 fontes backend coincidentes.
  O único alerta de governança é MAIN_BEHIND_RELEASE:
  publicar main antiga causaria regressão.
- O navegador Playwright com os mesmos bytes servidos,
  API fictícia e sem credenciais, passou em 1365, 390 e
  320 px com Voltar/Avançar de projetos, abas, arquivos
  Markdown e foco acessível, zero exceções JS.
- A revisão de doc-01 a9ff48e foi preservada isoladamente
  como evidência, sem merge nem implantação paralela.
  Dev-02 manteve o próprio commit 5b3c908.
- A versão publicada continua sujeita ao aceite autenticado
  de Surface e à integração governada na main, que permanece
  defasada. T019 e T021 não liberam o release CloudIFF.

**Segurança do importador PGH:** o dev-02 também publicou
o importador que rejeita chaves JSON duplicadas, commit
interno 9474b93. A fonte Git corresponde ao arquivo
administrativo instalado, SHA256
d3e2190b7f74626d7344698a3b877e08419ec8fa9744d344bfde720a2aeb27f4.
A revisão independente doc-01 executou 9/9 testes de
JSON estrito, 11/11 de sanitização de textos sensíveis e
verificou os vínculos explícitos dos projetos, todos PASS.
Isso não implica sincronização em tempo real: a exportação
PGH/Atlas continua manual e precisa verificar frescor.

**G1:** o servidor Samba de backup ainda requer acesso
autenticado por identidade confiável e confirmação da
host key SSH por canal legítimo. Sem inventário de
compartilhamentos e teste real de restauração dos
serviços CloudIFF, G1 continua pendente mesmo após a
aprovação geral dos pedidos.

Os demais gates G0–G5 e a contenção/rotação das 22
origens Git com credenciais permanecem abertos; também
não há comprovação do E2E Docker para a promoção Hn→Pn.

## T022 publicado — auditoria de 18h40 UTC

Esta seção atualiza o estado do Atlas após a revisão
isolada do doc-01: **T022 está publicado pelo dev-02**,
sem alterar a situação dos gates de release CloudIFF.

- Branch Git interna Atlas:
  fix/dev02-atlas-t022-snapshot-open-tab-stale-20261115,
  commit **53021dd**. Backup do JS anterior foi preservado.
- SHA256 do JS efetivamente instalado e servido:
  33615c85793ca85dc120391ee57612499c59a4dfec2d08e4be047d74c27be60d,
  igual à fonte Git da branch de correção.
- Doc-01 revisou a proposta paralela em branch isolada
  review/doc01-atlas-t022-live-freshness-20261115,
  commit **67377d1**, que não foi implantada. A única
  diferença de JavaScript entre as duas versões é um
  comentário de esclarecimento.
- Playwright sobre os **bytes realmente servidos**,
  usando somente API sintética e relógio virtual:
  **3/3** resoluções 1365/390/320 exibiram estado
  old após 16 minutos e aviso de que o painel P0 não
  pode atestar segurança com dados antigos. O campo de
  busca manteve o foco/texto, sem exceções JS.
- Regressões com o mesmo JS de produção: T021 passou
  **3/3** Back/Forward de projetos, guias e Markdown;
  T019 passou **9/9** casos de foco H1.
- Auditoria read-only contra o commit correto: **3/3**
  arquivos frontend e **3/3** fontes backend idênticos
  ao Git. API saúde OK, acesso externo não autenticado
  HTTP401. Único aviso MAIN_BEHIND_RELEASE, porque
  a main Atlas não contém todos os fixes publicados.
- **Estado T022:** versão publicada e validada com
  testes sintéticos; aceite autenticado formal ainda
  depende de identidade de teste/secret_ref e Surface.
- A idade do snapshot agora é refletida corretamente
  numa aba já aberta, mas a alimentação PGH segue
  manual. Não equiparar correção de aviso de frescor
  a telemetria viva ou sincronização contínua.

### Outros gates operacionais atualizados

- **PR #40:** head 8365058, CI verde e 19 testes
  de journal durável PASS, incluindo fence global de
  número público e verificador externo de evidência.
  O componente continua standalone, não integrado
  ao worker ou à promoção real Hn/Pn. A auditoria
  identificou contenção potencial de transação SQLite
  quando o callback verificador é lento. Revisão de
  concorrência, trust boundary, crash e Docker E2E
  exigidos antes de qualquer implantação.
- **Agenda Única:** infraestrutura e desenvolvimento
  confirmaram divergência de porta do banco na API
  produtiva contra a homologação/serviço DB. O serviço
  segue reiniciando; corrigir somente com owner,
  backup restaurável, rollout canário e rollback.
- **Supabase Pooler:** configuração de porta do banco
  confere com a fonte DB, mas a causa de falha DNS/rede
  permanece sob investigação. Não alterar a porta
  indiscriminadamente.
- **P0/G0–G5:** as 22 origens Git com credenciais
  expostas, cofre OpenBao produtivo, prova de backup
  restaurável e rotação/revogação/re-auditoria
  ainda impedem a liberação CloudIFF v145.1.
## Revisão PR40 — proteção dos arquivos SQLite

Atualização de 15/11/2026, aproximadamente 19h UTC.

O PR #40 avançou para revisão 05d3978, com CI
aprovado e testes de verificador externo fora do
write lock SQLite. O journal permanece **isolado
e não integrado ao worker de produção**.

Doc-01 reproduziu em ambiente descartável que
o banco SQLite e seu arquivo WAL podem nascer
com modo **0644** quando o processo usa umask 022;
com umask 077, os arquivos ficam em modo 0600.
O resultado é dependente das permissões do
diretório de dados; **não existe evidência de
exposição produtiva** por esse achado.

Foi publicada uma proposta de correção na branch:

- https://github.com/debianlima/cloudiff/tree/review/doc01-pr40-private-sqlite-20261115
- Commit efbb1b0, baseado no PR #40, sem alterar
  a branch do responsável.
- Abrir/criar o banco com modo 0600, reforçar
  modo 0600 de arquivos antigos DB/WAL/SHM,
  rejeitar symlinks no componente final e
  arquivos não regulares.
- Testes de permissões **5/5 PASS**, testes
  próprios do PR40 **22/22 PASS** e suíte
  completa CloudIFF **1391/1391 PASS**.
  Validação estática de fonte: OK.
- Exigir revisão de dev-01, infra-01 e
  aud-01 antes de integrar ou publicar:
  proprietário, diretório ancestral confiável,
  ACL e concorrência multiworker.

**A proposta não substitui G0–G5:** o principal
P0 continua sendo a presença de credenciais em
22 configurações de origem Git. Sem restauração
produtiva comprovada, cofre OpenBao e Docker E2E
da promoção Hn→Pn, a v145.1 continua bloqueada.

## P1 em PR39 — permissão de homologação na fila

Auditoria independente de 15/11/2026, ~19h UTC.

O PR #39 (head 75a6b4a, draft/unmerged, CI verde)
contém revalidação de ACL para promover candidatos
à Produção. Porém o aud-01 encontrou outro caminho,
**específico da Homologação**, que ainda requer correção:

- A criação de job de homologação confere acesso
  genérico ao projeto, sem exigir a concessão
  específica de homologar.
- O worker recebe um job de homologação com
  autorização previamente presumida e não prova,
  novamente, o vínculo/role do ator na execução.
- A auditoria reproduziu a falta de guarda com
  **1/1 cenário negativo de enfileiramento** e
  **2/2 cenários negativos de revogação na fila**,
  em funções reais executadas com banco e Komodo
  inteiramente simulados. Não houve Hn real criada.
- O Portal ativo contém o mesmo padrão de chamadas
  segundo inspeção estática read-only; isso não
  equivale a confirmar abuso em produção.

**Critério de aceite F3/T010:** verificar concessão
de homologação no enfileiramento e novamente no
worker, com vínculo de ator/projeto/job/estado,
participação, role atual, candidate e tratamento
fail-closed de cancelamento ou revogação. Acrescentar
testes negativos e reauditoria independente antes
de merge/deploy. Não usar um sucesso de CI de
Produção como prova de segurança do fluxo Hn.

O responsável é dev-01 com colaboração de dev-02
e revisão aud-01/infra-01. A autorização do usuário
permite trabalhar na correção, mas não substitui
G0/G1, restore e o teste E2E em ambiente descartável.
## Revalidação independente — PR39/40 e Atlas T023

Atualização 15/11/2026, aproximadamente 19h40 UTC.
Aprovações continuam condicionadas às evidências dos gates.

### PR #39 — autorização de homologação corrigida no código

O dev-01 publicou novo HEAD **4eee31f**, CI
GitHub Actions success, PR draft/unmerged. O
doc-01 conferiu em worktree independente:

- Os dois arquivos espelhados do Portal são
  idênticos byte a byte.
- **39/39 testes de autorização PASS** no
  commit exato (incluindo fluxo de homologação).
- Enqueue Hn exige concessão de homologação;
  worker revalida ator, job, role e vínculo
  antes/durante etapas, protegendo cancelamentos.
- Ainda faltam prova de identidade atual para
  privilégios de Admin/Professor, lease interserviços
  e testes E2E de revogação durante efeitos Docker.
  **Não há autorização de merge/deploy.**

### PR #40 — arquivos privados do journal

O dev-01 publicou HEAD **28fa84f**, CI
GitHub Actions success, PR draft/unmerged,
incorporando a revisão doc-01 efbb1b0 com
preservação de autoria e validação adicional
do diretório pai. Na revisão independente:

- **22/22 testes originais do journal PASS**.
- **7/7 testes de permissões/ACL PASS**.
- Banco, WAL e SHM passam a ser controlados
  com modo 0600, mais verificação do diretório
  imediato antes da criação.
- O módulo permanece standalone; verificação
  de ancestrais, ACL efetiva, lease Docker e
  integração ao worker ainda exigem aprovação
  de infraestrutura/auditoria e teste isolado.

### Atlas T023 — metadados inválidos de frescor

O surface-01 identificou que dados sintéticos
recent/verified com idade ou limite inválidos
podiam ser apresentados sem aviso. O doc-01
preparou no Git Atlas interno a branch
review/doc01-atlas-t023-strict-metadata-20261115,
commit **f67bc65**, baseada no T022 publicado.

- Exige idade e limite numéricos finitos válidos
  e timestamp ISO8601 com fuso de horário.
- Caso inválido: estado old e aviso de que
  segurança não pode ser atestada, sem esconder
  tarefas P0.
- **42/42 testes Chromium sintéticos PASS**
  em 1365/390/320 px. Regressões T022 3/3,
  T021 3/3 e T019 9/9 também PASS.
- **T023 ainda não foi implantado**: revisar
  com dev-02, aud-01 e Surface, publicar somente
  com backup, paridade Git/runtime e rollback.

### G1 / operações pendentes

A infraestrutura comprovou que o agendamento do
backup PostgreSQL dos tenants terminou com
resultado success e sem falhas reportadas.
Entretanto, o armazenamento é root-only,
os artefatos atuais ainda não foram inventariados
pelo responsável nem restaurados isoladamente.
Portanto **G1 não está concluído**.

O CloudIFF v145.1 permanece bloqueado por G0–G5,
P0 de 22 origens Git com credenciais, falta de
OpenBao produtivo e Docker E2E Hn→Pn.
Os problemas do Agenda API, Pooler, cinco W1 502
e TLS SilviPro continuam sob diagnóstico
e owner autorizados.

## Atlas T023 publicado — auditoria e ajuste de fuso

Atualização 15/11/2026, aproximadamente 19h45 UTC.
Esta seção substitui a informação anterior de que
todo o T023 estava apenas em revisão.

- **T023 já foi publicado pelo dev-02**, commit
  Git interno **46ce086**, branch
  fix/dev02-atlas-t023-invalid-freshness-failclosed-20261115,
  com backup prévio da interface.
- JavaScript HTTP, arquivo instalado e Git coincidem
  por SHA256. Auditoria independente doc-01 confirmou
  **3/3 frontend e 3/3 backend iguais à fonte**;
  API healthy, HTTP 401 anônimo. Único alerta:
  MAIN_BEHIND_RELEASE, main Atlas ainda antiga.
- A implementação publicada recusa metadados de
  idade e limite inválidos e mensagens de
  snapshot_error, sem esconder tarefas P0.

### Caso residual em timestamp sem fuso

- A versão publicada utiliza Date.parse(timestamp)
  para validar snapshot_at. Em teste sintético
  reproduzido diretamente no código publicado,
  timestamp sem Z ou offset — por exemplo
  2026-11-15T18:00:00 — ainda retorna recent.
- A API real não foi observada emitindo esse formato
  inválido; trata-se de robustez fail-closed,
  não de incidente produtivo comprovado.
- Doc-01 criou proposta mínima sobre o commit
  publicado, branch interna
  review/doc01-atlas-t023-timezone-required-20261115,
  **commit ec3774b**, mantendo tratamento de
  snapshot_error e exigindo ISO8601 com fuso explícito.
- Testes com a proposta: **42/42** variantes
  Chromium em 1365/390/320 px, T022 3/3,
  T021 3/3 e T019 9/9 PASS, zero erros JS.
- **A correção de fuso ainda não foi implantada**.
  Dev-02 deve revisar e publicar com rollback;
  Surface retestar o hash servido após publicação;
  aud-01 conferir aviso P0 e fail-closed.

A instalação do T023 não comprova acesso autenticado
para T005, feeds individuais para os 22 projetos
restantes, backup restaurável do CloudIFF, OpenBao
produtivo ou conclusão de G0–G5. O gate de release
CloudIFF v145.1 permanece bloqueado.

## Acompanhamento 16/11 — PR39 final de permissões e G1

Verificação em 16/11/2026, aproximadamente 00h35 UTC.
Registro PGH por documentacao/cloudiff/doc-01, sem
alteração do Portal, Komodo, Docker, banco, secrets ou
serviços de produção.

### PR #39 — commit 6bdc5ca

A branch do dev-01 passou de 4eee31f para
**6bdc5ca**, CI remoto GitHub Actions
43754314973 **completed/success**. O PR permanece
**draft/open/unmerged**, e o Portal ativo em
Hospedagem ainda possui o código anterior ao fix.

Revisão independente doc-01 sobre cópia Git limpa
do commit exato:

- **56/56 testes direcionados de autorização PASS**,
  sem utilizar Portal, Komodo ou Docker reais.
- Os dois mirrors de cloudif_portal_publications.py
  têm conteúdo idêntico, SHA256
  fa85b68054693915c1653b6b3078c30ffdb207da1cebc4e88cf71556383cfe40.
- Testes adicionais: test_publication_jobs.py
  **4/4 PASS**, race/deploy **2/2 PASS**.
- Source validator scripts/validate.sh: OK,
  errors=[], sem alterações de código geradas.
- O teste completo scripts/test.sh independente
  atingiu timeout sob carga concorrente de agentes
  antes de emitir resumo final. **Não considerar
  full-suite independente aprovado**; o dev-01
  registrou sua própria execução completa
  1385/1385 PASS. O CI remoto deste HEAD está verde.
- A criação direta de Hn exige concessão de
  homologação atual; enfileiramento/execução de
  publicação legada exigem concessão de publicar,
  papel e vínculo atual com o job/snapshot.
- Alteração de alias público exige concessão de
  publicação. Operações desconhecidas no worker
  deixam de entrar no caminho legado implicitamente.
- O worker não pode assumir papéis Admin/Professor
  apenas a partir de uma string antiga na fila.
  A migração/inventário de jobs antigos deve
  ocorrer sob o owner, sem reproduzir jobs
  históricos automaticamente.

**Risco residual:** mudanças em Docker, rede ou
alias continuam vulneráveis à janela TOCTOU
após revalidação local sem lease/fencing entre
serviços; falta teste E2E com autenticação/ACL
atuais e efeitos externos, crash e rollback.
Não liberar PR39 para deploy somente pelo CI.

### PR #40 e backup G1

O PR40 head **28fa84f** continua draft e
não integrado aos handlers. SQLite DB/WAL/SHM
e diretório pai passam pelos testes de privacidade
do protótipo, mas faltam lease do worker,
verificador de evidência confiável, recuperação
real pós-crash e validação do diretório efetivo.

Infra-01 atestou que a rotina systemd de backup
PostgreSQL diário dos tenants terminou sem
falhas reportadas. O armazenamento root-only
não pode ser inspecionado por cti, e os artefatos
atuais **não foram restaurados isoladamente**.
Um sucesso de timer não conclui G1.
Não rebaixar ACL para coletar prova.

Os bloqueios P0 de 22 configurações Git com
credenciais embutidas, G0–G5 e o teste Docker
do mesmo Hn container promovido Pn persistem.
Atlas main segue defasada, PGH ainda depende
de importação manual e há apenas dois feeds
por projeto no catálogo de 24.

## Atualizacao 16/11 — Atlas reconciliado e fence multi-servico

Revisao por documentacao/cloudiff/doc-01,
2026-11-16, aproximadamente 07h30 UTC.
Estado comprobado por LabIFF, IPsec, testes
e hash de fontes, sem alteracao produtiva CloudIFF.

### Atlas

- A branch main Atlas interna ja foi avancada por outro
  agente para 0ec46a8; nao existe divergencia contra
  o commit T023 publicado.
- JavaScript, CSS e HTML servidos correspondem ao
  mesmo commit Git. Testes Node de hierarquia, P0,
  MD e Python de auditoria/importacao/vinculos passam.
- Snapshot PGH atualizado com exportador sanitizado:
  2026-11-16T07:15:07Z, **1046 eventos**, **6 journals**,
  **24 projetos**. Importador strict JSON efetuou dry-run,
  backup atomico e readback da API; HTTP401 anon externo.
- Os vinculos PGH sao explicitos para 2 projetos; nao
  inventar feeds de atividades para os outros 22.
- A main reconciliada elimina o risco anterior de
  republicar uma branch antiga. Nao significa que
  todas as tarefas CloudIFF estao concluidas.

### CloudIFF: adaptador do journal e autoridade real

- Dev-01 trabalha em branch local com lease exclusivo,
  integrando o journal PR40 ao worker Komodo. Aud-01
  desenvolveu revisao isolada para comparar o fluxo.
- Doc-01 criou uma terceira proposta independente,
  **somente revisao**, a partir do merge local dos
  PR35/38/39/40 (HEAD 7bd3468). Commit GitHub
  **8f5ec20**, em
  https://github.com/debianlima/cloudiff/tree/review/doc01-crosspr-release-guard-20261116
- Contrato do adaptador: identidade atual, lease
  cross-service, journal duravel com mutating antes
  de qualquer efeito Docker/rede, callback recebe
  operation_id e contexto do lease, prova externa
  autenticada para committed. Falha incerta exige
  needs_reconciliation, nunca retry cego.
- Testes **11/11** novos, journal **22/22**,
  permissao SQLite **7/7**, rollback **19/19**,
  source validator OK. Nenhum Docker real.
- **Nao esta ligado ao worker produtivo**; o lease
  entre hosts e a autoridade de evidencias ainda
  precisam existir. A publicacao no GitHub nao
  realiza merge dos PRs nem release.
- O modulo alternativo do dev-01 com flock
  local nao e, por si, um lease entre servicos.
  Compatibilidade com modo disabled nao deve
  ser tratada como durabilidade efetiva. Owner,
  infra e auditores precisam comparar os codigos.

### Infraestrutura e gates

- O arquivo local .git-credentials no LabIFF tem
  modo 0600 sob pasta 0700; seu conteudo nao
  foi lido ou alterado por esta revisao.
- Os **22** arquivos .git/config remotos com
  credenciais em URL (Forja21, Hospedagem1)
  ainda necessitam contencao/rotacao e G5.
  Nao significam 22 tokens unicos.
- SSH BatchMode do LabIFF para Hospedagem com
  a identidade disponivel retornou Permission
  denied. Nao foi usada senha do chat,
  nem houve bypass SSH ou acesso root remoto.
- G1 nao comprova restauraçao real de PostgreSQL
  e volumes; G0 ownership, G2 OpenBao produtivo,
  G3 Docker Hn→Pn, G4 rotacao e G5 reauditoria
  permanecem sem aceite.
- Agenda API DSN 5432 versus banco 54402,
  Pooler DNS, W1 cinco 502 e TLS SilviPro
  continuam pendencias de servico.
- **CloudIFF v145.1 continua bloqueado.**

## 16/11 — candidato G4 e adaptador de journal auditados

Atualizacao 16/11/2026, aproximadamente 07h40 UTC.
Todas as implementacoes abaixo sao REVISAO DE CODIGO;
nao substituem owner/locks, secret_ref ou testes reais.

### G4 — contencao de permissoes Git

- Branch de revisao GitHub
  https://github.com/debianlima/cloudiff/tree/review/doc01-g4-owner-git-config-mode-20261116
  commit **3266a2e**.
- Ferramenta owner_git_config_containment.py executa
  plan sem revelar paths ou URLs; apply apenas com
  root, service user proprietario, contagem exata,
  manifesto root-private e verificacao de integridade;
  chmod dos configs sensiveis a 0600, sem mudar URL.
- Rollback exige manifesto original root-only e
  confirmacao expressa por poder restaurar modo
  world-readable. Rejeita symlink, hardlink, file
  replacement e owner/diretorios inseguros.
- **12/12 testes sintéticos PASS** e um teste
  CLI completo sobre repo descartavel no LabIFF:
  plan, apply 0644->0600, manifesto root0600,
  rollback sem confirmacao negado e restauracao
  controlada PASS. Validator de fonte PASS.
- **Nao aplicado aos 22 arquivos reais** (Forja21,
  Hospedagem1) por falta de acesso autenticado/owner
  aos hosts. Mesmo aplicado, G4 exigiria rota de
  credenciais por secret_ref, revogacao e rotacao,
  mais reauditoria G5. Contencao nao e rotacao.

### T003/T006 — fencing duravel revisado

- Branch de revisao GitHub
  https://github.com/debianlima/cloudiff/tree/review/doc01-crosspr-release-guard-20261116
  commit **8f5ec20**, baseada no merge local
  7bd3468 dos PR35/38/39/40 do dev-01.
- Adaptador independente obriga identidade atual,
  lease entre servicos, prepared/mutating antes de
  efeitos externos e prova independente para commit.
  Falha ambigua permanece needs_reconciliation.
- **59 testes direcionados PASS**: 11 do adaptador,
  22 journal, 7 ACL DB/WAL/SHM e 19 rollback.
  Validator de fonte PASS.
- Dev-01 e aud-01 ja possuem wrappers em worktrees
  com lease proprio; essas abordagens devem ser
  conciliadas, nao sobrepostas automaticamente.
- O novo adaptador NAO foi integrado a handlers
  produtivos. Flock local nao e lease distribuido,
  e provider ficticio nos testes nao comprova Docker.
  Sem atestado real e identidade/TTL de servico,
  nao habilitar enforcement nem afirmar durabilidade.

### Estado de infraestrutura neste ponto

- .git-credentials LOCAL LabIFF ja tinha 0600 e
  diretorio 0700; nenhum ajuste necessario.
- SSH nao interativo para Hospedagem recusou
  autenticação com identidade disponivel.
- Atlas PGH exportado sanitizado em 07:15:07Z:
  1046 eventos / 6 journals / 24 projetos,
  importador strict com backup/readback OK.
- Atlas main ja havia sido reconciliada para
  0ec46a8 por outro agente, sem acao concorrente;
  a versao servida passou nos testes de paridade.
- Permanecem nao comprovados G0 owner/locks,
  G1 backup PostgreSQL/volumes restauravel,
  G2 OpenBao prod, G3 Docker Hn->Pn, G4 token
  revocation/rotation e G5 verificacao final.
- Agenda API DB port mismatch, Pooler DNS, cinco
  W1 502 e SilviPro TLS permanecem em diagnostico.

**CloudIFF v145.1 nao esta liberado.**

## 16/11 — Atlas PGH automático e atualizações PR41/45/46

Revisão 16/11/2026 aproximadamente 21h06 UTC,
documentacao/cloudiff/doc-01.

### T007 — sincronização Atlas PGH realmente implantada

- O IPsec passou a sincronizar snapshots PGH automaticamente
  a cada dez minutos por atlas-pgh-sync.timer (enabled/active).
- A conexão via VPN 10.20.0.3 → 10.20.0.5 é feita com
  chave SSH dedicada, host key verificada e comando
  forçado de exportação, sem shell arbitrário.
- No LabIFF, o exportador executa efetivamente como
  mcp-shell sem privilégios root. No IPsec, a chave
  privada está em diretório protegido root-only.
- O cliente valida JSON estrito, integridade, origem
  e fuso da data, conteúdo sanitizado e vínculos
  de projeto; o importador Atlas oficial faz dry-run,
  backup e troca atômica sob lock.
- Bloqueio conservador para menos de 2 GiB livres
  no volume de backups; nunca apaga backups antigos
  automaticamente. É necessária política de retenção.
- Código, unidades systemd, documentação de rollback
  e 14 testes versionados no Git interno Atlas,
  branch review/doc01-atlas-pgh-autosync-20261116,
  commit **251140d**. Main não foi alterada pela
  revisão; o serviço existente e a versão Git
  têm hash idêntico.
- Execuções periódicas confirmadas durante o dia.
  Snapshot 2026-11-16T20:59:27Z com **1167 eventos**,
  seis journals íntegros e catálogo de 24 projetos;
  API saudável e acesso anônimo externo HTTP401.
- Testes novos 14/14 PASS; regressões P0/controle
  Markdown/hierarquia, audit10/10, JSON9/9 e
  filtro texto sensível11/11 PASS.
- Apenas **dois** projetos possuem feeds PGH
  próprios explícitos. Não atribuir os eventos
  transversais aos demais 22 projetos.

### PR41 — validação de alias no worker

- GitHub PR41 atual HEAD **35cb187**, CI Actions
  43954728713 SUCCESS, permanece draft/unmerged.
- Em análise independente doc-01 o handler real
  de ativação manual contém condição SQL por
  project, publication_number, public_number e
  status ready ANTES dos efeitos externos.
- Testes de binding de alias **2/2** e do gate
  **20/20** PASS no commit exato; validador de
  fonte PASS. A vulnerabilidade de public_number
  identificada pelo aud-01 não se reproduz nesse
  HEAD de código.
- PR46 contém revisão isolada do mesmo defeito;
  comparar antes de reaplicar para não duplicar
  mudanças. PR41/46 continuam não implantados.
- O worker ainda precisa lease distribuído,
  identidade real e verificador independente
  Docker/banco/alias, crash recovery e G0–G5.
  Uma aprovação de CI não autoriza release.

### PR45 — identidade Komodo planejada, não criada

- Infra-01 publicou PR45 draft, CI success,
  com instruções e gerador de payload não secreto
  para criação de svc-pgh-cloudiff por administrador.
- O catálogo Atlas registra estado
  PENDING_ADMIN_CREATION; **não há conta, API key
  nem secret_ref produtivo comprovados**.
- O owner Komodo com admin autenticado deve
  criar a conta e atribuir apenas Read ao alvo
  estritamente necessário. Somente depois,
  broker/OpenBao produtivo poderá fornecer
  chaves de curta duração com escopo mínimo,
  e aud-01/surface-01 executar testes de negação.
- Não reutilizar usuário de sessão, criar chave
  sem validade ou assumir direitos a partir
  de manifesto pendente.

Os bloqueios G0 (delegação efetiva/lock), G1
(restore institucional Postgres, roles e volumes),
G2 (OpenBao produtivo), G3 (Docker Hn→Pn E2E
e lease), G4 (remover e revogar credenciais
expostas em 22 configs Git) e G5 (reauditoria)
continuam impedindo CloudIFF v145.1.

## 17/11 — contas de integração preexistentes

Atualização doc-01 a pedido do responsável CloudIFF.

- Contas históricas distintas: cloudif-bot é Git Provider do
  Forgejo usado pelo Komodo; cloudif-agent era usuário técnico
  do Komodo com privilégios delegados; cloudif-integrator pertencia
  à integração Tuleap. Nenhuma delas foi autenticada via
  Komodo Core nesta auditoria. Histórico não prova grant atual.
- A nova svc-pgh-cloudiff permanece em PR45 como
  PENDING_ADMIN_CREATION. Não criar duplicata até reconciliar
  identidade existente, escopo, revogação e owner por API autenticada.
- Guia permanente para agentes:
  docs/PGH-COFRE-OPENBAO-IDENTIDADES-E-PERMISSOES-2026-11-17.md,
  replicado no LabIFF como
  GUIA-COFRE-OPENBAO-IDENTIDADES-E-PERMISSOES-CLOUDIFF-2026-11-17.md.
- O guia ensina a solicitar secret_ref por PGH Credential Broker,
  exigindo identidade autenticada, machine_ref, service_ref,
  capability, projeto e TTL; testes allowed/denied, revogação,
  owner, change-ID e bloqueios quando autenticação não existe.
- AGENTS.md compartilhado e roteiros operacionais de infra-01,
  aud-01 e surface-01 apontam para o guia. As seis identidades
  infra-01, aud-01, dev-01, dev-02, surface-01 e doc-01 receberam
  referência COF-OpenBao-Runbook-20261117 e nota PGH.
  DOCTOR_OK validou as cinco áreas.
- OpenBao IFF2 homologação v2.6.2 saudável e broker SSH
  preexistente autenticado somente no transporte não
  comprovam OpenBao produtivo nem escrita KV. Komodo Core
  responde HTTP200, sem sessão admin comprovada.
- G0–G5, migração/rotação Git P0 e testes produtivos permanecem
  obrigatórios. Este runbook não concede acesso por si só.
