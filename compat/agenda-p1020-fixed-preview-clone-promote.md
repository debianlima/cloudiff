# Agenda P1020 — correção Preview fixo → clone H → promoção in-place P

**Vigência:** 20/11/2026. **Contrato:** `docs/PADRAO-CLOUDIFF-PREVIEW-HOMOLOGACAO-PRODUCAO-20261120.md`.

Esta unidade substitui a interpretação temporária anterior que criava ambientes H/P independentes para o Agenda Única.

## Semântica implementada

1. **Preview W1:** permanece o mesmo slot/URL e continua sincronizado ao Forgejo. Nenhum novo Preview é criado por commit.
2. **Homologação Hn:** o executor congela e clona o runtime do Preview, incluindo rootfs, configuração privada de runtime e dados de volumes graváveis. A H deixa de acompanhar o Forgejo depois da clonagem.
3. **Produção Pn:** o deployment H aprovado muda de papel para Produção **sem recriar containers**. O `deployment_id` e os IDs Docker dos serviços permanecem os mesmos; somente metadados/bridges/roteamento/ativação são alterados.
4. **Troca de H/P:** a nova instância é validada antes da anterior ser desativada. Desativação normal para runtimes Compose preserva containers/volumes para rollback e não executa remoção destrutiva.
5. **Fail closed:** o caminho antigo de `deploy(snapshot, production)` fica bloqueado com `compose-production-requires-homologation-promotion`.

## Deltas incrementais

Os releases Compose ativos ainda não possuem sua origem completa reconciliada na árvore Git. Por isso esta correção é preservada como patches incrementais sobre os arquivos ativos imediatamente anteriores à mudança, sem copiar binários inteiros para a fonte antiga.

| Componente | Patch | SHA-256 do patch | SHA-256 ativo resultante |
| --- | --- | --- | --- |
| Executor | `agenda-p1020-fixed-preview-clone-promote-executor.patch` | `3f47120b4864fa10e65bccadb73a02738e7cee500730f9d31c18cd8314a6c68d` | `3a9593fd548625d15e9ab18e42a52ec1732e3f20dfddec4402703b57f1ae83b0` |
| Broker | `agenda-p1020-fixed-preview-clone-promote-broker.patch` | `637935dc3501af51fbbb3770fe18a8e58af3380c52a81a450c05bba72042544b` | `77740a791f27157481a3b85f434be4ba9ea23591e7d22a1d3f55c89d9f4084f6` |
| Portal | `agenda-p1020-fixed-preview-clone-promote-portal.patch` | `e6c02b17b342ef73859db4653a6e7d7ca95ee40693a4d12c0dcb088e9f4f53c0` | `c19654f9a07a94013696ea52c1c43f82e5d71d82a6beb8877eab7c6376ac142e` |

`PATCH_REPRODUCIBILITY=PASS`: aplicar cada patch ao backup imediatamente anterior reproduz byte a byte o SHA-256 do arquivo ativo.

## Provas executadas

- W1 remoto Forgejo = W1 checkout = `e32213d0b4d22fe5ff69241aaf5fdc33eb3f8d78`.
- Preflight W1: `READY`; URL pública continua no mesmo slot.
- Plano H atual: `execution_allowed=true`, sem blockers, origem `e32213d...`.
- Plano P antigo por novo deployment: `execution_allowed=false`, blocker `compose-production-requires-homologation-promotion`.
- Plano de promoção: ação `deployment.compose-snapshot.promote-in-place`, `sameDeploymentRequired=true`, `containerRecreationForbidden=true`.
- Teste de promoção usando cópia temporária do banco do executor e H4 apenas como fixture de leitura: mesmo `deployment_id`, mesmos IDs Docker antes/depois, `containersRecreated=false`, registro de auditoria de promoção criado na cópia temporária.
- Nenhuma promoção real de H4 foi executada; P2 permaneceu intocada.

## Patches anteriores superados

`agenda-p1020-compose-executor-isolation.patch` e `agenda-p1020-compose-broker-gates.patch` ficam preservados apenas como histórico. Eles representam a interpretação temporária anterior de H/P isolados e **não devem ser aplicados** após a decisão humana de 20/11/2026.

## Próximo gate

A criação de uma H nova continua exigindo a rota autenticada do Portal. H4 é legado do fluxo anterior e não declara `sameInstancePromotionRequired`; portanto não deve ser usada como candidata de Produção do novo contrato. O próximo candidato deve ser criado novamente a partir do W1 atual pelo fluxo oficial.
