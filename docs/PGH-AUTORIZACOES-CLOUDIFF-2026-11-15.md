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
