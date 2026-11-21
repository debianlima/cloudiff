# Agenda P1020 — delta incremental sobre releases `a9-compose`

## Objetivo

Preservar, de forma reproduzível e auditável, somente as correções específicas do
Agenda Única aplicadas aos releases Compose ativos em 20/11/2026, sem substituir
as fontes versionadas antigas por binários ativos cuja procedência Git ainda não
foi localizada.

## Executor multissserviço

- release ativo de base: `multiservice-deployment-executor/a9-compose-ac7fe40`
- base SHA-256: `985f6440d2a33165d4f8539c11038c438c6d38eb69ae9597da6350367d7c4a7f`
- patch: `compat/agenda-p1020-compose-executor-isolation.patch`
- patch SHA-256: `c41603c4b7ee12c7fa9f8d852e6a48ac928fc9e01d30cc8bc7db9cd0b62e51d9`
- resultado esperado SHA-256: `b7ca4d620a58812a5fd48fdf7af775d5c355c7ba4b0f593e9ff66e011cd93c72`

O patch adiciona apenas a política `agenda-v1`: snapshot sem valores de ambiente W1
nem conteúdo do volume PostgreSQL W1, remoção de ambiente W1 no destino, volumes H
vazios, volume estável de Produção, bloqueio de bind gravável, derivação de
`APP_REVISION`, backup pré-release e restauração automática do volume de Produção
em falha.

## Deployment Broker

- release ativo de base: `deployment-broker/a9-compose-794fb0e`
- base SHA-256: `7a909b6c1ddea7e3d30fc221243e8d68248abf5d14e9ee11d9258ae25490f070`
- patch: `compat/agenda-p1020-compose-broker-gates.patch`
- patch SHA-256: `5c8b946bea8e67a9a6c18da8d1a8f70c087629f8b1223b27528bd912bcd0f4ed`
- resultado esperado SHA-256: `1207d003c762f594c04c4994a63fdbbd1b1e9578870055eace3b21f1ee1accb0`

O patch torna o plano fail-closed para ambiente sensível/dados persistentes,
aceita apenas capability `agenda-v1` com cobertura completa de variáveis do
destino, exige prova de snapshot sanitizado, política de volume por ambiente e
rollback de Produção, e corrige
a projeção de `primaryService` ao fundir identidade do projeto com a configuração
runtime versionada.

## Portões de reconciliação

- `DELTA_INVENTORY=PASS`: base, patch e resultado possuem hashes observados.
- `LEARNING_PRESERVED=PASS`: os patches foram produzidos contra os releases ativos
  originais e não substituem o código pré-existente de Compose.
- `PATCH_REPRODUCIBILITY=PASS`: aplicar cada patch ao respectivo base produz
  exatamente o SHA-256 do binário ativo.
- `RECONCILIATION_CLOSURE=BLOCKED`: a árvore Git atual possui executor de 461 linhas
  e broker de 783 linhas, enquanto os releases `a9-compose` possuem contratos
  Compose mais novos; o commit/origem que gerou esses bases ainda não foi
  localizado. Até localizar essa origem, os patches são registro de delta e não
  autorização para copiar o binário ativo inteiro sobre a fonte antiga.

## Segurança

Os patches não contêm valores secretos. Eles referenciam somente nomes de
variáveis e contratos de resolução. Valores H/P permanecem no secret store do
CloudIFF e nunca entram neste repositório.

## SUPERADO PELO CONTRATO W/H/P DE 20/11/2026

Os patches de isolamento documentados neste arquivo permanecem somente como evidência histórica. A implementação vigente está em `agenda-p1020-fixed-preview-clone-promote.md` e segue: Preview fixo sincronizado → clone integral/congelado para H → promoção da mesma instância H para P, sem rebuild/reclone. Não reaplicar os patches antigos de H/P independentes.
