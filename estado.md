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
- A skill de projeto vigente é `cloudiff@0.1.38`.
- Decisão humana de 09/09/2026: novas funcionalidades e refatorações do CloudIFF devem ser modulares por responsabilidade; adapters/entrypoints apenas orquestram e lógica específica vai para módulo coeso próprio, com gate que impeça regressão monolítica.
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
- sem unidade ativa após o fechamento de `CLOUDIFF-A10-E2E-FOLLOWUP`; nova unidade deve registrar `manifesto.yaml.trabalho_compartilhado` antes do primeiro artefato.
- A reserva textual anterior de CLOUDIFF-A9 expirou em 2026-09-10T00:48:00Z sem renovação canônica posterior; não foi ressuscitada como lock ativo.
- U27 foi substituída após exceder `previsao_termino` em mais de 30 minutos sem renovação/atividade observável; o bloco original foi registrado fora do repositório antes da troca.

## Competências ativas na U20
- `cloudiff@0.1.35`.
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

## A10 — Portal v2/legacy, UX e hardiness

- Lane isolada `cloudiff-a10`; reserva canônica em `manifesto.yaml.trabalho_compartilhado` antes das alterações funcionais.
- A10-UX-01: `CloudIF-Professor` recebe o link **Serviços globais**, mas o runtime vivo responde 403; o patch alinha leitura ao papel global sem abrir o formulário mutante de backup, que continua sob `user.admin`.
- A10-UX-02: confirmação inválida reproduzida sem ação destrutiva como `409 invalid_confirmation` seguida, com o mesmo token, de `409 wizard_required`; o patch valida a confirmação antes de consumir o token single-use.
- Ajuda: CTA **Abrir Administração** passa a ser emitido somente para `CloudIF-Tenants-Admin`; o texto educativo permanece para os demais perfis.
- Exclusão/Publicação: mensagens conhecidas viram texto acionável; modal de exclusão bloqueia fechamento desde o POST inicial, recebe/restaura foco; wizard de Publicação fecha com `Escape` e restaura foco.
- Hardiness vivo: 240 GETs autenticados em cinco personas e oito superfícies produziram zero 5xx/erros de transporte; crawl professor em profundidade 2 encontrou somente os 403 já classificados (Serviços globais, Produção intencional e Administração via CTA corrigido).
- Fonte integrada em `main@2727e726f79dd36b0692e716943e7ad2fe80523f` e preservada também em `origin/cloudiff-a10`; regressão integral pós-aplicação na lane: **1080/1080 PASS**; suíte focal **83/83 PASS**; `py_compile`, `git diff --check`, secret scan e `scripts/validate-repository.py` PASS.
- C++ não acionado: a amostra de latência/RSS não provou hot path CPU-bound; o maior custo observado no perfil admin veio acompanhado de payload/escopo global substancialmente maior.
- Gate visual permanece **NÃO VERIFICADO/BLOQUEANTE PARA ACEITE**: WebDev oficial Selenium/noVNC existe em Forja, porém as origens disponíveis não possuem rota/allowlist funcional até o serviço. Nenhuma regra de rede foi ampliada.
- Produção permanece inalterada; nenhum deploy/cutover foi autorizado ou executado por A10. Revalidação do runtime **pós-patch** permanece pendente porque o release vivo não foi promovido.
- Handoff preparado para `WV-A09` / chat `6a940f36-4a58-83e9-b1ed-45773207f056`; próximo agente deve reservar a própria zona antes de editar.


## A10-VISUAL — validação real do Portal e acessibilidade mobile

- Reserva canônica `A10-VISUAL` ativa antes das alterações funcionais; zona ampliada para incluir `portal/design/**` antes do primeiro patch CSS.
- WebDev/Selenium oficial recuperado sem ampliar firewall/allowlist; Grid Selenium 4.46.0 com Chrome 150 usado para navegação real. O relay de homologação permaneceu GET/HEAD-only, com métodos mutantes bloqueados.
- O primeiro preview parcial foi descartado como evidência de `main` porque `cloudif_portal_v2_coexist.py` fixa `LIB=/srv/cloudif/lib` e, portanto, carregava `portal/ui`/`portal/design` do runtime instalado. A homologação válida foi repetida em mount namespace privado contendo os libs + `portal/` exatos do working tree, mantendo produção `18094` intacta e candidato isolado em `18104`.
- Browser real desktop e mobile `390x844`: Visão geral, Publicações, Aprovações, Projetos, Bancos e tenants, Backup, Conectores, Serviços globais, Excluir projeto, Ajuda e tema escuro sem overflow horizontal de documento.
- Correção funcional: o wizard **Novo projeto** agora registra o acionador e restaura foco após `Escape`/fechamento; Chrome real confirmou foco de retorno ao botão **Novo projeto** em desktop e mobile.
- Correção de teclado: Tema, Perfil e sidebar mobile passam a fechar por `Escape`; foco retorna ao respectivo acionador. O modal **Conexões remotas** já fechava e restaurava foco e permaneceu equivalente.
- Correção mobile: acionadores Tema/Perfil, opções do seletor de tema, logout no card de perfil e links secundários da navegação contextual têm mínimo de 40 px quando interativos. Chrome real confirmou Tema/Perfil `40x40`, opções do tema com 40 px e logout com 40 px.
- O falso positivo de logout “offscreen” foi descartado por `details.open=false` + `checkVisibility=false`; a versão integral de `main` também eliminou o aparente overflow de Reconciliação observado no preview parcial.
- Gate visual final: PASS no candidato integral. Sidebar abre/fecha em 390 px sem overflow; `Escape` fecha e restaura foco; navegação contextual de Aprovações usa `project-context-current`, não possui `project-context-group`, e fica integralmente dentro da viewport.
- Testes: suíte focal final 34/34 PASS; regressão integral do Portal **1082/1082 PASS**; `py_compile` PASS; `git diff --check` PASS; `scripts/validate-repository.py` PASS com zero erros após remoção do bytecode gerado pelos testes; secret scan PASS. `node --check` não pôde ser usado como gate neste executor porque o Node local sofreu falha nativa de V8 e o host de homologação não possui Node; o `app.js` atualizado foi, porém, carregado e executado pelo Chrome 150 real durante os probes acima.
- C++ não acionado: nenhum hot path novo com benchmark de latência/RAM justificou migração; esta unidade permaneceu estritamente UX/acessibilidade.
- Produção continua inalterada. O gate canônico permanece fechado até provar `R-REDES -> pfSense real -> SSH legítimo`; adicionalmente, mudanças em superfícies congeladas exigem autorização humana explícita separada. A ordem automatizada de supervisor não foi tratada como essa autorização.
- Patch versionado em `49a74e64635a1a64872f4850f36f084031bc15bb`, preservado em `origin/cloudiff-a10-visual` e integrado por fast-forward em `main`.
- Cleanup de homologação: preview `127.0.0.1:18104` e relay A10 `172.21.0.1:18110` removidos; produção permaneceu HTTP 200 e `/srv/cloudif/app-pointers/portal-current` continuou apontando para `/srv/cloudif/app-releases/portal/hardness-missing-stack-ux-20260907T055809Z`.
- Reserva `A10-VISUAL` liberada canonicamente ao final; nenhum artefato produtivo foi mutado.

## A10-RELEASE-GATE — R-REDES/pfSense e preparação fail-closed

- Reserva canônica `A10-RELEASE-GATE` registrada antes dos artefatos; escopo posteriormente ampliado para `deploy/a10-release-gate/**`, `skills/cloudiff/SKILL.md`, `competencias.yaml` e `tests/test_cloudiff_project_skill.py` antes de tocar esses caminhos.
- O diagnóstico anterior `BLOCKED_CAMPUS_EDGE` foi superado em 09/09/2026: `10.250.255.254` voltou a responder e se identifica live como **R-REDES** (RB2011/RouterOS 7.22). O mesmo equipamento possui `172.16.0.2/24` em `vlan900-firewall`.
- R-REDES aprende `172.16.0.1` em ARP como `BC:24:11:D3:4C:5E` e recebe 3/3 pings do pfSense em ~0,6 ms. `ad2` (`10.68.128.253`) usa gateway/rota `10.68.128.254` (R-REDES) para `172.16.0.1`, com ICMP PASS e TCP/22 OPEN. Assim, **R-REDES -> VLAN900 -> pfSense real -> serviço SSH** está provado.
- O último elo permanece bloqueado por autenticação: o pfSense anuncia `publickey,password,keyboard-interactive`, mas `admin@172.16.0.1` rejeita a credencial operacional disponível mesmo forçando `keyboard-interactive,password`; nenhuma senha/chave foi resetada, importada ou persistida. Novo gate: **`BLOCKED_AUTH_PFSENSE`**.
- A Hospedagem `10.62.92.7` também é alcançável a partir de `ad2` pelo gateway R-REDES; ICMP e TCP/22 passam, enquanto TCP/18094 externo permanece fechado como esperado. `cti@10.62.92.7` rejeita a credencial operacional e as chaves locais gerenciadas testadas em `BatchMode`, inclusive com negociação explícita `keyboard-interactive,password`. Novo gate adicional: **`BLOCKED_AUTH_HOSPEDAGEM`**.
- Por causa desses bloqueios de autenticação, `portal-current`/`portal-previous` live não foram revalidados neste ciclo e nenhum snapshot antigo foi promovido a verdade atual.
- Dependência arquitetural comprovada: `cloudif_portal_v2_coexist.py` fixa `LIB=/srv/cloudif/lib`; portanto um release coerente do Portal exige o mesmo source set para **app em `portal-current` + overlay `/srv/cloudif/lib` + `/srv/cloudif/lib/portal`**. Trocar apenas o symlink do app pode reproduzir candidato falso com bridge/assets antigos.
- `deploy/a10-release-gate/build-candidate.sh` prepara bundle imutável/hashado desses três planos; `preflight-target.sh` captura current/previous, service metadata, hashes e pre-state sem trocar ponteiro/reiniciar; `rollback.sh` é fail-closed e exige sentinel + integridade do pre-state. Não existe script de promoção/aplicação deliberadamente.
- Build local validado: 124 arquivos, manifesto SHA-256 completo, `promotion_authorized=false` e `requires_live_preflight=true`; `bash -n`, manifest hash parity, secret scan e `scripts/validate-repository.py` PASS.
- Bundle final versionado/preparado a partir de `e706cab4f3ec057bf577e1b4768267039ed28cb1`: `a10-ux-e706cab4f3ec.tar.gz`, SHA-256 `f2c8750eba29cb720e70c65bfedbe7183c2b3a7f1793ef6539fb1feee9e0750a`. O bundle não foi copiado/aplicado na produção.
- O gate `tests/test_cloudiff_project_skill.py` continha drift histórico: hardcodes de `cloudiff@0.1.5`, método `@14`, 13 referências fixas e comparação do working tree atual com hashes do snapshot v1→v2. A implementação dinâmica histórica de `839c9e8` foi restaurada e generalizada: versão/referências derivam do frontmatter, o snapshot preserva sua integridade histórica e `FROZEN_SURFACES.md` continua validando as quatro superfícies congeladas atuais. Gate final: `CLOUDIFF_PROJECT_SKILL=PASS version=0.1.35 compoe=2 referencia=14 anti_cycle=PASS`.
- Skill reconciliada para `cloudiff@0.1.35` com L057: candidato do Portal só é válido quando app, lib e pacote v2 vêm do mesmo source set. `competencias.yaml` acompanha a mesma versão.
- Produção não foi promovida. Próximo gate obrigatório: recuperar autenticação SSH legítima no pfSense e Hospedagem; executar `preflight-target.sh` no alvo; somente então revisar mecanismo de cutover coerente e autorização antes de qualquer mudança produtiva. Reserva `A10-RELEASE-GATE` encerrada ao final desta preparação.

## CLOUDIFF-A9 — Publicações: visão resumida antes do gerenciamento (2026-09-09)

- Autorização humana explícita no chat atual para ajustar a superfície **Publicações**, preservando a Visão geral como está.
- Fluxo novo no candidato isolado: `?tab=publicacao` mostra somente resumo por publicação (projeto, estado, endereço, versão ativa e ação **Gerenciar publicação**); nenhum formulário mutante é renderizado nessa tela.
- O gerenciador completo permanece em `?tab=publicacao&project=<slug>`, onde os controles de endereço, versões e publicação continuam disponíveis.
- Compatibilidade de ownership ajustada para schemas em que `projects.created_by` ou `project_tenants` não existem; `owner` existente não é mais perdido por uma exceção de schema.
- Chrome 151/CDP real validou desktop 1440x900 e mobile 390x844: 2 cards sintéticos, 0 formulários mutantes na lista, 0 overflow, `Meus sites` correto, botão mobile com 44 px; clique abre o gerenciador com formulários administrativos somente no detalhe.
- Testes focados: `portal.tests.test_publication_management_ui`, `portal.tests.test_grouped_resources` e `portal.tests.test_frozen_surfaces_contract` => 19 testes, OK.
- Regressão `test_publication*.py`: sem falha funcional nova observada; os erros estruturais dependem de `components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py`, ausente neste checkout.
- Perfil C++: `clean_general_publication_body` com 100 cards/200 execuções => p50 6,8804 ms (~68,8 us/card); rota HTTP candidata => p50 225,7 ms em 10 requisições. Classificação: **não é hot path CPU relevante**, portanto `cpp_migration=NOT_TRIGGERED` nesta unidade.
- Produção não foi alterada por esta unidade; candidato de validação permanece isolado em loopback para continuidade da revisão.

## CLOUDIFF-A9 — requisito de arquitetura modular (2026-09-09)

- Decisão humana: modularidade passa a ser requisito do CloudIFF e das próximas unidades do projeto; evitar concentrar novas responsabilidades em arquivos monolíticos.
- Contrato prescritivo registrado em `docs/REQUIREMENTS.md` (`R-MOD-1`) e `docs/ARCHITECTURE.md`; skill do projeto elevada para `cloudiff@0.1.37` com `ModularidadeObrigatoria` e aprendizado L058.
- Aplicação imediata no ajuste de Publicações: `portal/core/html_fragments.py`, `portal/core/resource_ownership.py` e `portal/core/publication_summary.py` isolam responsabilidades; `portal/core/legacy_shell.py` permanece como adaptador/orquestrador e caiu para aproximadamente 281 linhas nesta revisão. O CSS específico foi isolado em `portal/design/publications.css` e incluído explicitamente na allowlist de assets do adapter v2.
- Gate modular/UX final: 22 testes focados OK; `CLOUDIFF_PROJECT_SKILL=PASS version=0.1.37`; Chrome 151 confirmou desktop/mobile com asset modular carregado, `padding=0`, zero overflow e botão mobile de 44 px. `scripts/validate-repository.py` permanece vermelho pelos mesmos 13 paths ausentes do `HEAD`, com `new_errors=[]` e `portal_v2_important=0`.
- A mesma disciplina vale para C++: componente nativo modular por responsabilidade; migração só após profiling/benchmark que prove hot path, com contrato e rollback/fallback preservados.
- Método global recarregado após homologação da decisão: `desenvolvedor-de-software@16` é a linha homologada vigente para as próximas unidades; referências históricas a v15 permanecem como evidência de unidades anteriores.

## CLOUDIFF-A9 — Publicações: separação Ambiente × Promoção (2026-09-09)

- Decisão humana a partir da revisão visual das três telas: **Ambiente de publicação** é a central técnica dos ambientes Preview/Homologação/Produção e preserva `Visão geral`, `Site`, `PHP`, `Node.js`, `Terminal` e `Variáveis`; **Gerenciar publicação** é exclusivamente o fluxo de promoção `Preview → Homologação → Produção`.
- A página individual ganhou `← Voltar às publicações`; `Variáveis por ambiente` foi renomeado para **Ambiente de publicação** e abre em `Visão geral`, sem perder as ferramentas existentes.
- O gerenciador de promoção foi extraído para `portal/design/publication-release.js`: três abas, sem sub-menu Site/Terminal, sem Variáveis, sem `Recriar da Produção`, sem `Recriar do template` e sem a ação combinada `Homologar e publicar`. Preview tem uma ação primária (`Enviar Preview para homologação`), Homologação separa `Homologar` da rejeição, e Produção expõe `Publicar em Produção` quando elegível.
- Preview não exige mais o botão manual `Preparar/Sincronizar Preview` no gerenciador: ao abrir o fluxo sem Preview saudável, o frontend chama uma única vez o endpoint já existente `preview/ensure`; falha vira nota contextual com `Tentar preparar Preview`, não um bloco vermelho dominante na página principal.
- Jobs históricos `failed` deixam de ocupar a página individual como alerta principal; jobs `queued/running` continuam visíveis e erros da preparação/promoção permanecem contextualizados dentro do gerenciador.
- A capacidade solicitada **Preview atual → template base para próximos projetos** ainda não existe no contrato backend atual. O backend possui `template → recriar Preview` e snapshots da base editável, mas não Preview→Template; por isso nenhum botão enganoso foi criado. Essa capacidade exige unidade backend própria antes de ser exposta.
- Gate UI: 35 testes focados (`release_flow_wizard_ui`, `publication_management_ui`, `grouped_resources`) PASS; `py_compile` e `git diff --check` PASS. O suite backend W/H/P continua bloqueado no bootstrap pelo path ausente `components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py`, problema estrutural preexistente deste checkout.
- Chrome 151/CDP com `release-flow` sintético (sem mutação de infraestrutura) validou desktop 1440x900 e mobile 390x844: botão de voltar presente, dois menus apenas, gerenciador com 3 abas e 0 ferramentas técnicas duplicadas; `preview/ensure` automático observado e ação final `Enviar Preview para homologação`; Ambiente de publicação abre com as 6 ferramentas e `Visão geral` ativa; zero overflow mobile.
- C++ permanece `NOT_TRIGGERED`: esta alteração é principalmente navegação/DOM/JS e o renderer Python de Publicações já foi medido como fração não relevante da latência da rota; não há hot path CPU novo que justifique migração nativa.

## CLOUDIFF-A9 — Publicações: permissão por projeto e feedback de promoção (2026-09-10)

- Decisão humana: todo membro atualmente vinculado ao projeto pode preparar Preview e enviá-lo para Homologação; dono, `CloudIF-Tenants-Admin` e `CloudIF-Professor` homologam/publicam por padrão; outros membros recebem **Homologar** e/ou **Publicar** por delegação explícita.
- A gestão passa a ocorrer no botão **Permissões** dentro de Gerenciar publicação; a tela genérica de Aprovações deixa de ser o caminho primário para uma publicação iniciada por ator já autorizado.
- Admin mantém capacidade implícita e irrevogável pelo projeto; Professor pode administrar as delegações dos membros. Delegações ficam inertes quando a identidade deixa de constar na ACL do projeto.
- Segurança do worker: o ator de um job não é promovido artificialmente a Admin; `project_permission` é validado no enqueue e vinculado a candidato, número P e digest do ambiente antes da execução. O modo `critical_approval` antigo permanece compatível.
- Teste operacional no Tuleap: W1 ficou saudável; job 32 concluiu H3; H3 foi homologado pela identidade da sessão às 00:12:19Z. O estado intermediário `https` revelou um problema de feedback e agora a aba Homologação mostra **Criando candidato imutável / Candidato em preparação** durante o job.
- Gate desta extensão: 41 testes focados PASS (`publication_permissions`, `release_flow_wizard_ui`, `publication_management_ui`), `py_compile` e `git diff --check` PASS; enqueue direto validado em DB temporário com `authorization_mode=project_permission`, sem criação de `production_activation_requests`.

- Compatibilidade refinada: ao publicar pelo novo `project_permission`, approvals genéricos pendentes anteriores do mesmo projeto são cancelados/superseded; isso evita que H3 ou candidatos antigos continuem aparecendo como pendência ativa quando o usuário já está publicando por H4 ou posterior.


## CLOUDIFF-A10-E2E-FOLLOWUP — gaps comprovados pelo hardness E2E (2026-09-10)

- Hardness E2E anterior comprovou duas divergências: após um polling transitório, o backend de criação chegou a `status=succeeded` mas o cabeçalho do modal permaneceu em **Confirmando provisionamento / reconectando ao provisionador** até reload; e a exclusão administrativa de tenant concluiu sem remover `/var/lib/cloudif/user-workspaces/<tenant>.env`.
- Correção do modal: `settleProvisionTerminal(data)` assenta explicitamente título, texto, botão de fechar e flag `provisioning` em `succeeded/failed` depois de `drawLive(d)`, preservando o retry existente. Mirrors current/legacy recebem o mesmo contrato.
- Correção de tenant: a prévia inclui o `.env` gerenciado como presença; a exclusão remove somente o caminho exato do tenant, falha fechado se não conseguir removê-lo e o gate final exige sua ausência. A auditoria não copia o conteúdo do arquivo; grava somente metadados técnicos de remoção.
- Testes foram escritos antes do patch e reprovaram individualmente (`RC=1/1`); após a correção, os dois focados passaram e a suíte focal executável passou 33/33. Um teste adicional cobre o caso órfão em que somente o `.env` permanece.
- `py_compile` e `git diff --check` passaram. `scripts/validate-repository.py` voltou ao baseline conhecido de 13 `required path missing`; não há YAML inválido nem bytecode novo após limpeza. Os 5 erros da tentativa de regressão maior eram bootstrap por artefatos ausentes no checkout e não tocaram o código patchado.
- Gate de browser pós-patch não pôde ser repetido neste executor: `/dev/shm` estava em 99% com processo Chrome antigo de outra unidade; ele não foi encerrado. O E2E real pré-patch permanece evidência causal e a correção ainda não foi promovida ao runtime de produção.
- Tentativa alternativa pelo WebDev/Selenium oficial também ficou bloqueada: Hospedagem→Forja `10.62.91.2:17900/4444` expirou por timeout. Nenhuma rota/firewall foi ampliada para fabricar o gate.
- Fonte funcional integrada em `main@c9363101d1725f74b5a9e14fca5dac2d1c273f7b`; produção permanece inalterada e exige gate/autorização de release separado.
- Skill reconciliada para `cloudiff@0.1.38` com L059/L060; `competencias.yaml` acompanha a mesma versão. C++ permanece `NOT_TRIGGERED`: ambos os defeitos são estado de UI/cleanup de arquivo, sem hot path CPU medido.
