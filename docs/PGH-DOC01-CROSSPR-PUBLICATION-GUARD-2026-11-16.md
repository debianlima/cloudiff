# PGH — adaptador de publicacao com journal e autoridades externas

**Data:** 16/11/2026 UTC. **Revisao:** documentacao/cloudiff/doc-01.
**Base:** integracao local dev-01 HEAD 7bd3468 com PR35/38/39/40,
somente sandbox, sem alteracao do worktree reservado ao dev-01.

## Implementacao disponivel para revisao

Modulo:
components/runtime/current-apps/komodo-agent-current/cloudif_publication_operation_guard.py

Este modulo e um adaptador fail-closed ainda nao importado nas
rotas produtivas do Komodo. Ele reutiliza o journal SQLite do PR40.

A funcao execute_fenced_publication:
1. Exige autoridade de identidade que consulte grants ATUAIS.
2. Exige lease e fencing ENTRE SERVICOS, antes de gravar journal.
3. Grava prepared e mutating com commit duravel antes dos efeitos.
4. Entrega operation_id e contexto do lease a perform_mutation.
   O integrador precisa passar o fencing para cada operacao Docker,
   Nginx, alias, rede ou banco; a API local nao implementa isso.
5. Exige atestado e verificacao independentes do estado real
   de Docker, IDs de container, aliases e banco antes de committed.
6. Se ocorreu efeito sem prova final, deixa needs_reconciliation;
   novas tentativas para o projeto ou public_number sao negadas.

Uma resposta HTTP bem-sucedida ou result.ok=True nao prova
o estado externo. O verificador confiavel, lease de multiplos
servicos e fornecimento de identidade real ainda nao existem
neste codigo; nao se usam claims do request como autoridades.

## Testes executados

- 11/11 testes de contrato isolados com bancos SQLite temporarios:
  ausencia de verifier ou lease, perda de lease, revogacao ACL,
  abort antes de efeito, falha depois do efeito, resultado negativo,
  prova invalida, sucesso apenas com prova, retry ambiguuo negado.
- 22/22 testes existentes do journal PR40 PASS.
- 7/7 testes privados de arquivo DB/WAL/SHM e diretorio PASS.
- scripts/validate.sh: PASS, sem erros.
- Testes de Docker real e crash: NAO EXECUTADOS. O proof store
  dos testes e ficticio, nunca um atestado de producao.

## Passos obrigatorios para o owner integrar

- G0/G1: confirmar identidade, owner, change lock, backup de
  PostgreSQL e volumes, e restore isolado com rollback.
- G2: cofre OpenBao produtivo e secret_ref de servico; roles
  owner/delegated/Admin/Professor devem ser autenticados.
- G3: conectar adaptador nas rotas reais de release/activate;
  instalar lease com fencing respeitado por todos os mutadores;
  verificar mesmo ID de container Hn->Pn e ambiente, alias,
  banco, startup recovery e crash em Docker descartavel.
- Seguir fail closed em toda operacao needs_reconciliation,
  sem retry automatico, e exibir status em Portal/Atlas.
- G4/G5: conter, rotacionar e revogar credentials Git das 22
  configs identificadas; auditar novamente sem mostrar tokens.
- Dev-01 deve revisar codigo e integracao; infra-01/aud-01
  devem verificar autoridade de lease, armazenamento de prova,
  ACL de diretorios e concorrencia real; Surface deve validar
  E2E autenticado apenas com credenciais via secret_ref.

**Estado:** adaptador implementado e testado offline, SEM wiring
no worker, sem deploy, merge produtivo ou release CloudIFF v145.1.
