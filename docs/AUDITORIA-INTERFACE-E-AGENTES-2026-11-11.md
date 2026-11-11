# Auditoria de interface e agentes — 2026-11-11

Status: **evidência operacional + revisão de source**. Este documento não substitui contratos, `FROZEN_SURFACES.md`, Project-Skill, gates de release ou decisão humana.

## 1. Escopo e método

A auditoria confronta quatro fontes independentes:

1. source canônico `debianlima/cloudiff` em `main`;
2. contratos, testes e documentação do projeto;
3. runtime observado em Hospedagem (`10.62.92.7`), Forja (`10.62.91.2`), Mauricio (`10.62.91.3`) e Faro (`10.62.91.5`);
4. referências externas de acessibilidade/operabilidade, usadas apenas como comparação de padrão, nunca como autoridade sobre o contrato CloudIFF.

Classificação usada neste relatório:

- **observado**: medido diretamente em source/runtime;
- **derivado**: conclusão obtida pela combinação de evidências observadas;
- **indisponível**: não foi possível provar nesta unidade.

## 2. Resumo executivo

A interface evoluiu de um monólito legado para uma base v2 modular e hoje está em condição arquitetural muito melhor do que a registrada no plano de agosto. O maior risco de interface deixou de ser o Portal principal e migrou para duas frentes: coexistência com fallback legado e crescimento do `mcp-gateway`.

Nos agentes, a situação é inversa: os serviços especializados estão majoritariamente ativos, mas o **agente-base C++ e seu updater estão failed nos quatro nós auditados**. Há ainda um incidente P0 independente na distribuição do certificado NATS: a rota HTTPS máquina-a-máquina retorna 403 por uma allowlist baseada em IP que vê o gateway Docker `172.18.0.1`, não o IP privado original. O certificado NATS servidor observado vence em **2026-11-18**, portanto essa falha de distribuição tem janela curta para correção.

## 3. Interface — estado atual

### 3.1 Arquitetura observada

| Medida | Estado 2026-11-11 | Classificação |
|---|---:|---|
| Módulos `portal/modules/*` | 7 (`admin`, `delivery`, `environments`, `health`, `overview`, `projects`, `taiga`) | observado |
| Endpoints declarados no Portal v2 | 32 | observado |
| `cloudif-admin-portal.py` atual | 18.455 bytes / 144 linhas | observado |
| `portal/ui/shell.py` | 13.076 bytes / 287 linhas | observado |
| `portal/design/components.css` | 101.161 bytes / 926 linhas | observado |
| `!important` no design system v2 | 0 | observado |
| Arquivos de teste do Portal | 228 | observado |
| CI | `validate.sh` + `test.sh` | observado |

O item mais importante é a redução do antigo monólito do Portal: o plano de 2026-08 registrava ~345 KB; o entry point atual mede 18 KB e delega responsabilidades para módulos. A migração por coexistência/strangler está, portanto, produzindo o efeito esperado.

### 3.2 Design system e responsividade

O design system v2 usa `tokens.css`, `base.css` e `components.css`; não há `!important` nesses arquivos. `components.css` contém 34 regras `@media`, sete usos de `:focus-visible`, estados `aria-current`, diálogos e adaptações específicas para mobile.

A Visão geral atual aplica progressive disclosure em duas camadas:

- primeiro nível minimalista com **Projetos**, **Recursos** e **Plataforma**;
- dentro de cada categoria dinâmica, lista vertical + detalhe único (master/detail);
- seleção do item não acompanha apenas foco: o detalhe remoto é carregado somente após ativação explícita;
- item selecionado usa `aria-current=true` e estado visual distinto do foco.

Esse comportamento é compatível com a orientação do WAI-ARIA APG: disclosure deve expor estado aberto/fechado; foco e seleção devem permanecer distinguíveis; quando a troca de painel envolve latência/rede, seleção automática ao mover foco é indesejável.

### 3.3 Performance e carga progressiva

Evidência live registrada durante a evolução da Visão geral:

| Operação | Tempo observado |
|---|---:|
| primeiro paint da Visão geral antes do master/detail final | ~0,002 s |
| lista `publications` | ~0,003 s |
| lista `data` | ~0,003 s |
| lista `platform` | ~0,002–0,005 s |
| lista `academic` após master/detail | ~0,002 s |
| detalhe acadêmico isolado `mvplanner` | ~3,07 s |

Conclusão derivada: o custo mais alto do acompanhamento acadêmico foi retirado do caminho crítico da página e agora só ocorre no item explicitamente selecionado.

### 3.4 Pontos fortes

- superfícies congeladas continuam explícitas em `portal/FROZEN_SURFACES.md`;
- layout v2 único, navegação canônica e coexistência controlada;
- design system sem `!important` novo;
- lazy loading real, não apenas ocultação de HTML já carregado;
- foco visível e estados de seleção diferenciados;
- mobile possui breakpoints específicos para shell, projetos, publicação, Taiga e overview;
- releases A10 usam candidato imutável, pre-state, `current/previous`, readiness e rollback.

### 3.5 Dívidas e riscos de interface

#### P1 — fallback legado ainda aceita grupos administrativos de domínio

`portal/core/rbac.py` está correto e restringe administração ao `CloudIF-Tenants-Admin`. Entretanto, o fallback legado ainda possui referências a `domain admins`/`Domain Admins` em `cloudif_rbac.py`, `cloudif_ui_pages.py`, `project_action_safe.py` e snapshot legado.

Na Hospedagem, `cloudif-admin-portal.service` não injeta `CLOUDIF_ADMIN_GROUPS` por `portal.env`; portanto os defaults legados precisam ser tratados como risco real nas rotas que ainda caem em fallback.

Ação recomendada: eliminar concessões por grupo de SO/domínio nos caminhos ainda executáveis e provar a matriz de autorização em teste de coexistência antes de retirar compatibilidade.

#### P1 — `mcp-gateway` tornou-se o novo monólito

`components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py` mede **428.302 bytes / 3.636 linhas**. O plano antigo apontava 123 KB; a complexidade cresceu enquanto o Portal principal foi modularizado.

Ação recomendada: aplicar ao gateway a mesma política de extração modular já usada no Portal, separando OAuth/autorização, change-set, artefatos, approvals e proxy de ferramentas.

#### P2 — `components.css` tornou-se grande

O arquivo atual está limpo de `!important`, mas concentra ~101 KB e 926 linhas. O risco não é cascata quebrada, e sim coesão: muitos domínios (publicação, Taiga, projetos, overview, conexões remotas) compartilham o mesmo arquivo.

Ação recomendada: manter `tokens.css` e `base.css` globais, mas permitir folhas por módulo (`projects.css`, `publication.css`, `taiga.css`, `overview.css`) montadas pelo shell; o gate deve continuar proibindo `!important` e literais fora dos tokens.

#### P2 — mobile precisa de prova visual contínua

A captura móvel fornecida durante a operação mostrou uma tela de Projetos com títulos repetidos (`Tenant / Projetos` e `Workspace / Projetos`) e muito espaço vertical. A autorização já foi corrigida e o usuário passou a ter seis projetos visíveis, mas esta unidade não produziu uma nova captura pós-login real do mesmo dispositivo.

Ação recomendada: adicionar smoke visual mobile (viewport estreito) à prova de página real para Projetos, Visão geral e Publicações.

## 4. Agentes — estado atual

### 4.1 Inventário de source

A regeneração do catálogo técnico encontrou:

| Medida | Estado |
|---|---:|
| aplicações `*-current` em control-plane + runtime | 41 |
| referências estáticas de rota | 691 |
| unidades/timers versionados em `components/*` | 179 |
| declarações estáticas de tabela | 271 |
| current-apps control-plane | 30 diretórios |
| current-apps runtime | 11 diretórios |
| current-apps proxy | 2 diretórios |

O binário C++ `cloudiff-agent` concentra um agente-base de heartbeat e seis modos especializados observados no `main.cpp`: publisher, artifact executor, runtime executor, MCP upload, secure distribution e admin observability.

### 4.2 Runtime observado por nó

#### Forja `10.62.91.2`

Ativos relevantes: Forja agent Python, Komodo agent Python, runtime executor C++, artifact executor C++, executores de preview/homologação/produção e node metrics.

Falhas relevantes:

- `cloudiff-v2-agent.service`: failed; `natsConnection_Connect: Timeout`;
- `cloudiff-v2-agent-updater.service`: failed; HTTP 403;
- `cloudif-tuleap-ptbr-reconciler.service`: failed (adjacente, fora do agente-base).

#### Mauricio `10.62.91.3`

Ativos relevantes: publisher C++ live, publisher C++ auxiliar, secure distribution e gateways de acesso.

Falhas relevantes:

- `cloudiff-v2-agent.service`: failed; `No server available for connection`;
- `cloudiff-v2-agent-updater.service`: failed; HTTP 403.

#### Faro `10.62.91.5`

Ativos relevantes: runtime worker shadow, Taiga reconciler e Taiga.

Falhas relevantes:

- `cloudiff-v2-agent.service`: failed; `natsConnection_Connect: Timeout`;
- `cloudiff-v2-agent-updater.service`: failed; HTTP 403.

#### Hospedagem `10.62.92.7`

Ativos relevantes: control plane C++, worker C++, MCP upload C++, admin observability C++, Portal, registry, brokers, reconciliadores e APIs.

Falhas relevantes:

- `cloudiff-v2-agent.service`: failed; `No server available for connection`;
- `cloudiff-v2-agent-updater.service`: failed; HTTP 403;
- `cloudiff-v2-cert-sync.service`: failed; HTTP 403;
- adicionalmente, `cloudif-control-plane-integrity.service`, backups administrativos e `cloudif-ui-security-review.service` aparecem failed e devem ser tratados em unidade operacional própria.

### 4.3 P0 — rotas headless quebradas pela allowlist no NPM

Três superfícies máquina-a-máquina dependem do host `cloudiff.duckdns.org`:

- `/__cloudiff_agent_updates/`;
- `/cloudiff/portal/api/node-recovery-policy`;
- `/__cloudif_distribution/`.

Os blocos Nginx usam `allow 10.62.x.x; deny all;`. Entretanto, o access log live do OpenResty mostra as requisições de distribuição chegando como:

```text
client: 172.18.0.1
request: "GET /__cloudif_distribution/v1/collections/nats-server-cert/manifest ..."
access forbidden by rule
```

Portanto, a allowlist compara o IP **após a passagem pela bridge Docker**, não o IP original do nó. A consequência observada é HTTP 403 antes de Portal/serviço.

Isso não deve ser corrigido aceitando `172.18.0.1` indiscriminadamente: qualquer tráfego que alcance a mesma bridge passaria a parecer a mesma origem. A fronteira correta precisa preservar uma identidade confiável do peer ou mover o controle de origem para uma camada que ainda conheça a origem real (firewall/socket dedicado, proxy protocol/real-ip confiável ou endpoint interno separado), mantendo token/capability como segunda barreira.

### 4.4 P0 — certificado NATS servidor perto do vencimento e sync quebrado

Evidência observada em Hospedagem:

- certificado servidor: `CN=nats.cloudiff.duckdns.org`;
- validade: `2026-08-20` a **`2026-11-18`**;
- `cloudiff-v2-cert-sync.service`: failed por HTTP 403;
- o access log confirma que o 403 ocorre no NPM antes da SecureDistribution.

Conclusão: mesmo que a sessão NATS atual seja recuperada por outra causa, a distribuição do certificado precisa ser corrigida antes de 18/11 para evitar uma falha previsível.

### 4.5 P0 — agente-base não estabelece sessão NATS

Nos quatro nós, TCP para `10.62.92.7:14222` (ou loopback na Hospedagem) está acessível e os certificados cliente observados são válidos até 2028. Mesmo assim, o `cloudiff-v2-agent.service` falha ao conectar.

O erro exato de protocolo não foi isolado nesta unidade. O teste genérico `openssl s_client` não é um oráculo suficiente para NATS porque o protocolo pode preceder o handshake TLS; portanto o achado aceito é somente:

- TCP disponível;
- material cliente presente e não expirado;
- libnats do agente não estabelece conexão;
- heartbeat do agente-base não deve ser considerado saudável enquanto `cloudiff-v2-agent.service` estiver failed.

Próxima unidade deve executar `test_nats_mtls` com as credenciais/certificados reais, inspecionar o NATS server e provar reconnect sem restart.

### 4.6 P1 — updater e policy dependem do mesmo ingress quebrado

`deploy/agent_updater.sh` busca policy e manifest pela URL pública. Em todos os nós o serviço falha com 403. O mecanismo de atualização assinado continua correto em source (Ed25519, SHA-256, size, `current` atômico e rollback), mas o canal de distribuição está indisponível.

Ação recomendada: depois de corrigir a fronteira headless, executar em pelo menos dois nós:

1. policy GET;
2. manifest + assinatura;
3. atualização noop;
4. atualização para candidato controlado;
5. rollback por health failure;
6. prova de cooldown/recovery sem reboot indevido.

### 4.7 P1 — catálogos estavam desatualizados

Antes desta auditoria, `CATALOGO-DE-AGENTES.md` registrava 40 aplicações; a regeneração atual encontra 41. Rotas, serviços e dicionário estático também sofreram drift.

Ação recomendada: adicionar ao CI um gate que rode `scripts/generate-technical-catalogs.py` em workspace limpo e falhe se `git diff --exit-code` produzir mudanças.

## 5. CI, testes e observabilidade

O plano antigo dizia que o CI rodava apenas `validate.sh`; isso foi resolvido. O workflow atual roda:

- `scripts/validate.sh`;
- `scripts/test.sh`, que executa toda a suíte `portal/tests` e valida scripts de produção.

Gap atual: não existe um gate de integração que prove que as rotas máquina-a-máquina continuam acessíveis **a partir de uma origem autorizada real** depois de alterações do NPM/router. Os testes atuais verificam que blocos existem em texto, mas não detectam a transformação do `remote_addr` para `172.18.0.1`.

## 5.1 Reconciliação da suíte de testes durante a auditoria

A primeira execução completa de `scripts/test.sh` encontrou 1.318 testes, com quatro falhas e um erro. Nenhum estava nos arquivos de produção alterados por esta auditoria; a inspeção mostrou contratos de teste desatualizados ou frágeis:

- Taiga: a proteção de caminhos PHP continuava correta, mas o teste dependia de um `location /` escrito em uma única linha;
- Publicação: dois testes ainda exigiam `data-release-flow-open`, embora os contratos mais novos já exigissem explicitamente a sua ausência e a incorporação do fluxo em **Ambiente de publicação**;
- workspace de publicação: um teste não incluía a ferramenta `release`, adicionada por decisão homologada ao mesmo ambiente;
- integração Forja/Komodo: o teste provava paralelismo por um teto de tempo de 300 ms, tornando-se sensível à carga da máquina de CI.

Os testes foram reconciliados sem alteração de runtime: o paralelismo agora é provado por uma barreira de quatro threads; os demais verificam o contrato atual. Resultado final em quatro shards independentes:

| Shard | Testes | Resultado |
|---|---:|---|
| 1 | 307 | PASS |
| 2 | 395 | PASS |
| 3 | 302 | PASS |
| 4 | 314 | PASS |
| **Total** | **1.318** | **PASS** |

Também passaram a compilação do teste de segurança da UI e `bash -n` dos dois scripts de smoke/release usados por `scripts/test.sh`. `scripts/validate.sh` permaneceu PASS.

Uma thread assíncrona de teste de build ainda emite traceback de conexão/TLS em stderr em um cenário simulado, embora o teste correspondente termine `OK`. Isso é ruído de harness e deve ser eliminado em unidade futura para que stderr volte a ser um sinal confiável.

## 5.2 Correções executadas após a auditoria — 2026-11-11

Os P0 e o risco RBAC identificados acima foram corrigidos na unidade operacional seguinte. O texto das seções 4.3–4.6 permanece como evidência do estado encontrado antes da correção.

### NATS/heartbeat — resolvido

A causa do agent-base foi um drift de configuração: o source canônico já gerava `nats://10.62.92.7:14222`, com TLS habilitado separadamente por `CLOUDIFF_NATS_TLS_ENABLED=1`, enquanto os ambientes live usavam `tls://...`. A troca foi aplicada com backup por nó e canary no Faro.

Estado final observado:

- Forja, Mauricio e Faro: `CLOUDIFF_NATS_URL=nats://10.62.92.7:14222`;
- Hospedagem: `CLOUDIFF_NATS_URL=nats://127.0.0.1:14222`;
- os quatro `cloudiff-v2-agent.service` estão `active`;
- os heartbeats dos quatro nós continuam avançando;
- durante a rotação do certificado NATS, os quatro agentes preservaram o mesmo PID, provando reconnect sem restart do processo.

### Rotas headless — resolvido por mTLS

A allowlist por `remote_addr` foi removida das rotas de AgentUpdate/recovery/SecureDistribution. O controle de origem agora usa a PKI de agentes CloudIFF já existente. O NPM usa `ssl_verify_client optional` no host e cada rota headless exige `$ssl_client_verify = SUCCESS`; capability/bearer continua independente no SecureDistribution.

Gates live:

- sem certificado cliente: update/policy retornam HTTP 403;
- com certificado cliente CloudIFF: update/policy retornam HTTP 200 nos quatro nós;
- SecureDistribution foi comprovado pela sincronização real do certificado;
- Portal/browser sem certificado continua HTTP 302 para Authentik.

O source foi consolidado em `deploy/install_headless_routes.sh`; os antigos `install_agent_update_route.sh` e `install_secure_distribution_route.sh` foram retirados.

### Updater e certificado NATS — resolvidos

O updater passou a apresentar o certificado cliente já instalado em `/etc/cloudiff-v2/tls/`. Nos quatro nós, `cloudiff-v2-agent-updater.service` terminou `Result=success`, `ExecMainStatus=0`, com `AGENT_UPDATE=NOOP`, e os timers estão ativos.

A Hospedagem foi promovida para o consumer imutável `20261111-v23-secure-distribution-consumer-mtls`, preservando o v22 como `previous`. O sync substituiu o certificado que venceria em 18/11/2026 pelo certificado observado no provedor, válido até **17/01/2027 00:13:50 UTC**. `cloudiff-v2-cert-sync.service` terminou `success/0` e seu timer está ativo.

### RBAC legado — resolvido

`Domain Admins` foi removido de todos os caminhos executáveis de autorização CloudIFF auditados. O JSON histórico de permissões observadas foi mantido como evidência, não como regra de execução.

Release Portal: `a10-ux-207e60ecb1ef`; previous `a10-ux-86e4ea05d111`. Smoke live:

- identidade apenas `Domain Admins`: 0 projetos visíveis;
- `CloudIF-Tenants-Admin`: 6 projetos visíveis;
- `iff3546365` com Admin+Professor: 6 projetos visíveis;
- edge público sem sessão: 302 para Authentik.

A primeira tentativa de cutover foi revertida automaticamente porque o smoke esperava uma frase de vazio que a página não renderiza; o KPI real já era 0. O retry usou o critério correto e passou.

### Limpeza de legado — concluída com arquivo de recuperação

No Mauricio, 2.163 objetos `*.bkp*` antigos foram removidos da árvore ativa do NPM após prova de que nenhum rollback vigente os referenciava. Antes da remoção foram compactados e checksummed em `/srv/cloudif/backups/legacy-cleanup-20261111T100410Z/`. Os instaladores/state dirs headless v35 também foram arquivados antes da retirada.

Na Hospedagem, o state legado `agent-update-route-v35` foi arquivado em `/srv/cloudif/backups/legacy-cleanup-20261111T100416Z/` e removido do caminho ativo. Releases `current/previous` continuam preservados.

### Gates finais

- `scripts/validate.sh`: PASS;
- contratos headless/updater: PASS;
- testes focados de RBAC/Portal: PASS;
- suíte Portal em quatro shards: **1.318/1.318 PASS**;
- NPM `nginx -t`: PASS;
- CI agora falha quando os catálogos técnicos gerados deixam diff.

Source técnico: `207e60ecb1efc1f47954a5e68fa837fb515320b9`.

## 6. Priorização recomendada

| Prioridade | Unidade | Critério de aceite |
|---|---|---|
| **RESOLVIDO** | Corrigir ingress headless NPM | policy/update/distribution retornam sucesso de origens autorizadas e 403 de origem não autorizada; sem confiar cegamente em `172.18.0.1` |
| **RESOLVIDO** | Recuperar NATS agent-base | quatro nós `active`; heartbeat retomado sem restart após interrupção controlada; `test_nats_mtls` positivo/negativo PASS |
| **RESOLVIDO** | Renovar/sincronizar cert NATS | cert novo com lifetime suficiente instalado via SecureDistribution; timer PASS; NATS recarregado/reiniciado por contrato |
| **RESOLVIDO** | Remover admin por `domain admins` do fallback executável | tabela RBAC v2/legacy equivalente; somente grupos CloudIFF canônicos concedem global admin |
| P1 | Modularizar MCP gateway | módulos coesos, entry point fino, contratos/rotas invariantes |
| **RESOLVIDO** | Gate CI de catálogos | geradores não deixam diff em checkout limpo |
| **PARCIAL** | Gate E2E headless | teste real pós-router/NPM detecta 403 indevido |
| P2 | Dividir CSS v2 por domínio | nenhuma mudança visual; zero `!important`; tokens preservados |
| P2 | Smoke visual mobile | snapshots/DOM para 360–430 px em Projetos, Visão geral e Publicações |

## 7. O que não deve ser feito

- não remover o legado inteiro para “resolver” RBAC ou CSS; a migração continua incremental;
- não liberar `172.18.0.1` no NPM como atalho de correção da allowlist;
- não declarar agente saudável porque serviços especializados estão ativos;
- não usar `systemctl active` como substituto de heartbeat/reconnect;
- não mover segredos para Git, logs ou documentação;
- não substituir o Portal por framework novo enquanto as fronteiras modulares atuais estão funcionando.

## 8. Referências externas consultadas

- W3C WAI-ARIA Authoring Practices Guide — Disclosure e Keyboard Interface: https://www.w3.org/WAI/ARIA/apg/
- W3C APG Disclosure Pattern: https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/
- W3C APG Keyboard Interface: https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/
- NATS Documentation — resilient clients, reconnect e observabilidade: https://docs.nats.io/learn/

Essas referências orientam usabilidade/acessibilidade e resiliência, mas os contratos CloudIFF continuam sendo a autoridade operacional.
