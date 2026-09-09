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
- Recovery remoto do `mikrotik-work` esgotado no relay: peer/key atuais conferem; zero UDP de retorno do campus; handshakes forçados do peer atual para UDP/13231, 51820, 51821, 51822, 51823 e endpoint aprendido 4674 não obtiveram resposta; endpoint original foi restaurado. Próximo gate exige ação local/no lado MikroTik para fazê-lo voltar a originar o WireGuard Netmaker.
- Canal físico alternativo via host 116 esgotado: a NIC `eth0` não recebeu LLDP/802.1Q passivo; teste L2 efêmero com subinterface `eth0.900` não recebeu ARP de `172.16.0.1`/`172.16.0.2` e terminou com `VLAN900_ROLLBACK=PASS`.
- Canais alternativos de campus esgotados: `HARD01` não possui endpoint independente (peer histórico aponta ao mesmo edge público, sem handshake); não há port-forward SSH documentado para PELEGO, cujos acessos históricos foram apenas internos em `10.68.128.252`.
- Egresses Netmaker corporativos (`10.68.*` e `172.16.0.0/24`) estão vinculados exclusivamente ao node `pelego-ad` (`10.250.0.8`); não existe egress corporativo com outro node online.
- Busca passiva por hostname público de recuperação (`pelego`, `mikrotik`, `r-redes`, `router`, `gateway`) não encontrou canal DNS/certificado utilizável.
- Continuidade do relay Netmaker confirmada na janela da queda (~13:00 UTC): host sem reboot desde 06/09 03:17 UTC, container Netmaker iniciado em 06/09 03:18 UTC com `restart_count=0`, listener UDP/51821 ativo e sem evento de rede/restart correlato; a perda simultânea de `mikrotik-work`/`pelego-ad` fica localizada no lado campus/RouterOS.
- L2 físico dos peers PC confirmado como domínio D-Link: na 116, `172.16.0.1` responde em ARP com MAC `e0:1c:fc:99:3e:a4`, enquanto `172.16.0.2` permanece `INCOMPLETE`; portanto o MikroTik/R-REDES não está presente nesse segmento sobreposto.
- Link secundário da VPS Labiff confirmado: `wg-pgh` histórico (`10.20.0.5/32`) possui peer direto R-REDES/MikroTik `10.20.0.4` via `200.143.198.186:51823`; teste efêmero não obteve handshake e terminou com `WG_PGH_U21_ROLLBACK=PASS`.
- Fallback `wg0` da Labiff confirmado como recovery direto para R-REDES (`192.168.200.1/24` ↔ peer `192.168.200.2`, UDP/443, rotas campus); teste efêmero de 32 s não recebeu endpoint/handshake e terminou com `WG0_U21_ROLLBACK=PASS`.
- Ingress UDP/443 da Labiff validado externamente: datagrama de controle originado na LimaCripto chegou à `eth0` da Labiff; portanto OCI/firewall/listener da VPS não explicam a ausência de handshake do `wg0`. A falha do fallback fica localizada no peer R-REDES/MikroTik ou upstream dele.
- Revalidação ativa do `wg-pgh` secundário da Labiff confirmou iniciações WireGuard repetidas de `10.0.0.60:51824` para o endpoint R-REDES `200.143.198.186:51823`, com TX crescente e RX/handshake zerados; SSH/ping em `10.20.0.4` permaneceram indisponíveis e houve rollback completo.
- O `pgh-wg-failover.service` da 116 não oferece atalho independente para R-REDES: ele preserva o endereço canônico `10.20.0.2` alternando apenas entre caminhos VPS WireGuard/IPsec e policy routing `wg-vps`.
- Edge público permanece funcional durante o bloqueio atual: `cloudiff.duckdns.org` resolve para `200.143.198.186`; TCP/443 responde via openresty e, com SNI correto, `/cloudiff/portal/` retorna HTTP 200. Portanto pfSense/WAN/NAT até o Portal não estão totalmente indisponíveis.
- Correlação histórica relevante: T-047 registrou `VLAN900_ARP_L2_FAILURE_TOWARD_PFSENSE` com `vlan900` RUNNING mas sem MAC do pfSense aprendido no bridge. Como os três túneis externos do R-REDES estão sem retorno enquanto o edge público segue vivo, a hipótese operacional prioritária é falha no trânsito R-REDES↔pfSense/VLAN900 ou no default do MikroTik; **não há ainda prova live do `check-gateway`/ARP atual**, então essa hipótese não é promovida a causa confirmada.
- O SSH multiplexado oficial em `cloudiff.duckdns.org:443` está vivo (`OpenSSH 10.2p1`), porém o broker aplica `permitopen` somente aos destinos project-scoped já homologados (Forgejo `10.62.91.2:2222` e PostgreSQL de tenant); não há destino autorizado para MikroTik/pfSense.
- O WebDev read-only não é um bypass público: a rota `__cloudiff_webdev` permite somente `10.0.0.0/16`, `10.62.91.2`, `10.62.91.3` e `10.62.92.7`, nega o restante e encaminha para Forja `10.62.91.2:17900`. Os executores atuais em `10.250/16` recebem `403` por desenho; nenhuma allowlist foi ampliada.
- Forja possui probe oficial `cloudiff-network-health.timer` a cada 60 s com `rredes_icmp` para `172.16.0.2` e rota esperada via pfSense, mas sua evidência `/srv/cloudif/webdev-workspace/evidence/network-health.json` só é visível pelo WebDev read-only acima; sem origem autorizada atual, não foi contornado o gate.
- O IPsec legado da LimaEducation para `172.16.0.0/24` foi identificado como domínio D-Link sobreposto: `172.16.0.1` responde ICMP/HTTP/HTTPS e apresenta certificado TLS `O=D-Link`, enquanto `172.16.0.2` não responde como RouterOS; portanto esse túnel não alcança o verdadeiro R-REDES/pfSense.
- Executor independente em `10.0.0.86` está dentro da allowlist lógica do WebDev, porém não possui rota privada funcional para `10.62.91.2/10.62.91.3/10.62.92.7`; pelo domínio público, `__cloudiff_webdev` retorna `403`, indicando NAT antes da validação de origem. Assim, `network-health.json` da Forja continua inacessível sem ampliar privilégios/rotas.
- Probes UDP externos para `200.143.198.186` nas portas históricas do R-REDES (`51823`, `51822`, `4674`) não geraram retorno classificável; por natureza UDP isso é inconclusivo e não foi usado para afirmar remoção de NAT/port-forward.
- Não existe backup preservado de pfSense/RouterOS que documente a regra NAT/forward de UDP/51823; o inventário confirma apenas `wg-pgh` do MikroTik em `10.20.0.4/32`, UDP/51823. Logo a hipótese de NAT removido permanece não comprovada.
- O `network-health.json` live da Forja não é versionado/espelhado em Git; somente `cloudiff-network-health.py`, service/timer/install estão preservados. Sem WebDev autorizado ou acesso ao RouterOS, não existe snapshot live alternativo para `rredes_icmp`.
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

## U26 — Node Metrics C++ como autoridade de métricas de host

- O `cloudif-node-metrics-cpp` substitui o agente Python de métricas mantendo `/health`, `/metrics` e TCP/18096; a implementação Python foi retirada das árvores ativas e preservada apenas em `legacy/retired-agents/python/node-metrics/`.
- A candidata C++ teve shadow live desde 27/08/2026 e benchmark preservado na Hospedagem: paridade funcional do contrato, p50 de `/metrics` em poucos milissegundos contra centenas de milissegundos do Python e menor RSS.
- U26 acrescenta `storage.physical_total`, `storage.disk_count` e `storage.physical_disks`, permitindo ao Portal distinguir capacidade física instalada do uso do filesystem `/`.
- Releases live devem usar `/opt/cloudif-node-metrics/releases/<release>/` + `current` atômico e `release-manifest.json` com procedência; nenhum `.py` de node metrics pode permanecer em caminho ativo após cutover aceito.

## U26 — fechamento: Visão Geral 7/7 e Node Metrics C++

- Fechamento observado em 09/09/2026: a Visão Geral do Portal opera com `hospedagem`, `forja`, `mauricio`, `faro`, `backup` (`bocadesapo`/`10.68.128.250`), `pelego` (`10.68.128.252`) e `ad2` (`10.68.128.253`), com `node_count=7` e `online_count=7` após restart do `cloudif-admin-portal.service`.
- O Faro foi incluído como sétimo nó em `10.62.91.5:18096`; o pfSense possui regra restrita `10.62.92.7 -> 10.62.91.5:18096/TCP` com snapshot pré-mudança.
- Todos os sete nós usam `cloudif-node-metrics-cpp` no endpoint oficial TCP/18096, release atômica `/opt/cloudif-node-metrics/releases/u26-20260909-5fd5d89a/` com `current` e `release-manifest.json` de procedência.
- O mesmo binário foi construído em Ubuntu 24.04/glibc 2.39 e passou `--self-test` nos sete nós; SHA-256 observado da release: `d663beb57587f7fc3932bb688afa83b88b2169de84da73c0e7d41c50d00e8579`.
- Nenhum dos sete nós mantém `cloudif-node-metrics.py` em caminho ativo. Onde existia, a cópia pré-cutover foi preservada em `/var/backups/cloudif-retired-agents/python/`; no Faro não havia agente Python legado. O shadow C++ antigo da Hospedagem em `127.0.0.1:18196` foi desligado e arquivado separadamente.
- A apresentação diferencia `storage.physical_total` do uso de `disk_root`; valores destacados homologados: `backup/bocadesapo` ~3,0 TB físicos e `pelego` ~2,0 TB físicos. Os gráficos `Capacidade física por servidor` e `Uso de memória por servidor` estão presentes no HTML gerado da Visão Geral.
- Gate pós-restart do Portal: HTTP local `18094` = 200, `7/7` online e renderer contendo Faro, `3.0 TB`, `2.0 TB` e os dois gráficos.
- Inventário/dotfiles reconciliado em `44a0f7673b1801e16db142d7354963df3fbd5ded`; residentes Linux sincronizados nos sete nós.
