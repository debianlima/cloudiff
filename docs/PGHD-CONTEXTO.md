# PGHD Contexto — integração Home com PGH Core/Atlas Work

Status: EM MIGRAÇÃO / HOME PROJECT / ATLAS REGISTRATION PENDING APPLY

## Fronteira de ambientes

- `PGHD Contexto` pertence ao ambiente **Home**.
- `CloudIFF`/Atlas pertence ao ambiente **Work**.
- O Atlas cataloga e acompanha o PGHD Contexto, mas não transforma o projeto Home em projeto CloudIFF.
- PGH Core `164.152.61.172` pertence ao Work/núcleo e fornece Control Plane, Read-model, Access Admin, Vault Admin/OpenBao e RHGD.

## Componentes vinculados

- PGH Control Plane / PGA / PGD / RHGD;
- MCP PGHD Contexto (`pgh_context_next`, RAG e tools de access grant);
- PGH Access Admin — administração humana multiusuário/multiambiente;
- PGH Vault Admin / OpenBao — custódia e bindings de credenciais;
- PGH Network Flow — Homologação — read-model/observabilidade, migrando da Win110 para o Core;
- Win110 — origem legada do ControlPanel, Network Flow e função **Abrir Cofre**, preservada como rollback até o cutover.

## Estado técnico 2026-11-21

### Pareamento e acesso

O `pghd-server` foi pareado oficialmente como `principal:mobile.pghd_server_vps`, com capacidades mínimas `dashboard.read`, `agent.chat` e `model.chat`. O principal móvel não recebe `access.manage` automaticamente e Access Admin/OpenBao permanecem fail-closed.

### Read-model / bridge

Runtime observado:

- Control Plane `127.0.0.1:8790`: disponível;
- Read-model `127.0.0.1:8791`: indisponível;
- `management/live`: `CANONICAL_BRIDGE_UNAVAILABLE`;
- OpenBao `127.0.0.1:8200`: initialized/unsealed.

Pacote de recuperação versionado no `dotfiles`: preflight, restart da unit existente e resiliência `Restart=on-failure`, sempre com rollback e sem reinstalar a aplicação.

### Identidades SSH v2

Três identidades substitutas foram geradas e catalogadas por `key_id + fingerprint + secret_ref`; privadas permanecem fora do Git e cifradas. Públicas e installers aditivos estão no `dotfiles`. Nenhuma identidade antiga deve ser removida antes de autenticação nova, rollback e equivalência **Abrir Cofre**.

### OpenBao escrow

Bindings SSH estão planejados como `broker_injected`, com menor privilégio e TTL curto. O Core possui `pgh-vault-admin`, `pgh-vault-web-session`, OpenBao e `pgh-secret-migrate-window.py`. O escrow real continua condicionado à sessão administrativa humana e ao preflight do cofre.

### Network Flow

Destino canônico decidido: PGH Core, backend loopback `127.0.0.1:8793`, rota pública alvo `/dashboard/network-flow/` atrás da mesma autenticação do Dashboard. A instância Win110 `127.0.0.1:28900` permanece rollback até o cutover validado.

## Registro do projeto no Atlas

O Portal persiste projetos em `/var/lib/cloudif/portal/cloudif-portal.db`, tabelas `projects` e `project_acl`. O registro canônico esperado é:

- slug: `pghd-contexto`;
- nome: `PGHD Contexto`;
- tenant: vazio por padrão;
- owner: deve ser informado explicitamente por um administrador Atlas Work;
- descrição: projeto agregador Home, sem confusão com CloudIFF Work.

O projeto PGHD Contexto possui helper idempotente `tools/atlas_register_pghd_contexto.py` para dry-run/apply no host Atlas Work. Não inferir owner a partir de `principal_ref` PGH.

## Gates antes de retirar legado Win110

1. `READMODEL_8791=UP`;
2. `CANONICAL_BRIDGE=READY`;
3. `OPENBAO_ESCROW=PASS`;
4. `RECOVERY_FROM_OPENBAO=PASS`;
5. novas chaves v2 autenticam e rollback antigo continua válido;
6. `OPEN_VAULT_EQUIVALENCE=PASS`;
7. Network Flow Core validado;
8. janela de observação e auditoria independente.

Enquanto qualquer gate estiver pendente, ControlPanel/Network Flow/chaves históricas da Win110 permanecem preservados.
