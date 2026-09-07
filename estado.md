# Estado — 2026-09-07 — contrato v53

## Decisões vigentes
- A WAN pública do CloudIFF permite somente TCP/80 e TCP/443.
- SSH administrativo permanece apenas nas redes internas/VPN; não existe WAN/NAT público para 22.
- Conexões remotas de alunos usam **relay 443-only**: HTTPS e SSH compartilham a 443 pública; nenhuma porta de PostgreSQL, Forgejo SSH ou container é publicada.
- O botão **Conexões remotas** permanece como único acréscimo visual em Conectores e abre um `<dialog>`; a arquitetura de navegação não foi alterada.
- O Portal Authentik/ACL é a fonte de autorização. Cada ativação cria lease curta e chave Ed25519 temporária entregue uma única vez; o servidor armazena somente chave pública/fingerprint.
- Forgejo SSH usa destino interno direto `10.62.91.2:2222` pelo gateway.
- PostgreSQL/Supabase usa conector reverso da Hospedagem pela própria 443; o forward do tenant existe apenas enquanto há lease ativa e fica em loopback no proxy.
- Faro permanece fora do caminho e não foi modificado.
- A skill de projeto vigente é `cloudiff@0.1.29`.
- `PracticalSwan/frontend-design@2.0` é a competência de direção estética para futuras unidades de interface/redesign; não autoriza por si só alterar frozen surfaces.

## Decisões superadas
- FRP-Panel + faixa pública `24000-24999` — superado e removido; a regra NAT experimental e os runtimes FRP foram eliminados.
- Tratar porta dinâmica como superfície WAN — superado. A porta pública é sempre 443; o objeto temporário é a autorização/forward interno.
- Consultar o Portal a cada autenticação SSH — superado por cache local de leases atualizado em segundo plano, fail-closed.

## Evidências U19
- pfSense: removida regra legada WAN `Allow all ipv4+ipv6 via pfSsh.php`; permanecem apenas regras WAN TCP/80 e TCP/443.
- Sonda externa independente: 80/443 abertas; 22 e portas de serviço testadas fechadas/filtradas.
- HTTPS público continuou válido após multiplexação 443 (`cloudiff`, Forgejo e projeto 1010).
- SSH pelo mesmo `cloudiff.duckdns.org:443` alcançou Forgejo e devolveu `SSH-2.0-Go`.
- PostgreSQL do Teste Sofá respondeu ao SSLRequest através de SSH/443 + reverse relay da Hospedagem.
- Destino não declarado foi negado por `permitopen=`.
- Release de lease eliminou sessão já estabelecida em 21 segundos e cancelou o listener reverso de PostgreSQL.
- Browser Chromium móvel/dark: Conectores → Conexões remotas abriu overlay, Teste Sofá exibiu somente gateway público `:443`, entregou chave uma vez e voltou a “Ativar acesso” após Encerrar, sem erro JS.
- Teste Sofá foi devolvido a zero containers em execução ao final da homologação.

## Evidências U20
- PracticalSwan `frontend-design@2.0` fixada no commit `797f15729ca2d6a9756d7ae29409068cb971ebbf`.
- SHA-256 da fonte pública conferido: `e7c8e7fd0bde8eb8a7d9f024fe20eeab4b6cde3f612e8d253334b806c09ca1ff`.
- Registro adicionado ao catálogo `competencias-catalogo` e vinculado ao CloudIFF como `referencia`, não como cópia local.
- Nenhum arquivo de UI, CSS ou runtime alterado nesta unidade.

## Evidências U21
- Remodelagem canônica do Portal consolidada no workspace ativo com seletor compacto de projeto, um único projeto ativo em detalhe, menor densidade visual, temas claro/escuro e correção do fluxo de exclusão.
- Suíte Portal: **1070/1070 PASS**; `tests/test_portal_admin_observability.py` PASS; `scripts/validate-repository.py` sem erros; `node --jitless --check portal/design/app.js` PASS.
- Arquitetura de agentes preservada: os agentes CloudIFF v2 permanecem binários C/C++; nenhum runtime Python foi promovido como substituto.
- Release U21 permanece preparado e não promovido; produção continuou no release anterior durante todo o bloqueio de rede.
- Netmaker `pgh-p2p` foi reconciliado após testes de failover: `mikrotik-work` voltou a anunciar `172.16.0.0/24`, egress voltou ao PELEGO original e nenhum failover experimental permanece ativo.
- Evidência T-052 confirmou dois domínios L2 distintos usando `172.16.0.0/24`: o DIR-842 observado pelos PCs não substituiu o pfSense do domínio R-REDES. O caminho correto ao pfSense passa por R-REDES.
- A overlay legada `10.20.0.0/24` foi aposentada em 04/09/2026 em favor do Netmaker; testes efêmeros dos recoveries antigos `wg0`/`wg-pgh` não receberam handshake e foram removidos sem persistência.
- Cadeia administrativa vigente confirmada pelo operador: **Netmaker `10.250.0.0/16` → `mikrotik-work` (`10.250.255.254`) → PELEGO (`10.68.128.252`, node `10.250.0.8`) → domínio R-REDES/pfSense**. Não tentar PELEGO diretamente pelos hosts do domínio D-Link/PCs.
- Bloqueio operacional atual: **`BLOCKED_CAMPUS_EDGE`**. `pelego-ad` e `mikrotik-work` perderam conectividade no mesmo edge do campus por volta de 13:00 UTC de 07/09/2026; o primeiro salto legítimo ao pfSense ainda não está recuperado.
- Investigação do hypervisor pfSense continua historicamente bloqueada: guest KVM/QEMU UUID `ae1d9198-4e9a-4fd5-8035-23a662db60cf`, MAC `BC:24:11:D3:4C:5E`, nó/cluster Proxmox ainda não inventariado; T-028 exige acesso read-only autorizado ao DGS-1250 ou fonte de inventário/DNS equivalente.
- Gate de produção permanece fechado até provar `R-REDES -> pfSense real -> SSH legítimo`; somente depois executar Hospedagem, swap do release imutável U21 e smoke pós-promoção.

## Pendências fora do escopo
- U14: drawer vazio de **Gerenciar permissões** do Teste Sofá permanece separado.
- P2 do Teste Sofá continua dependente de duas aprovações humanas distintas admin/professor.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade U21, atualizado_em 2026-09-07T12:54:49-03:00.

## Competências ativas na U20
- `cloudiff@0.1.29`.
- `frontend-design@2.0` (PracticalSwan).
- `desenvolvedor-de-software@15`.
- `github-incremental-reconciliation@7`.
- `governanca-ontologica-de-skills@1.0.5`.
- `network-ssh-operations@1`.
- `operational-ui-truth@1`.
- `telemetry-data-visualization@2`.
