# Estado — 2026-09-03 — contrato v45

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre **somente para a interface web do CloudIF**: nenhum HTML/CSS/JS, navegação ou layout do Portal CloudIF pode ser alterado nesta unidade.
- A interface do projeto consumidor `GRUPix`/PagIF não faz parte do congelamento do CloudIF e poderá ser adaptada em unidade própria do repositório GRUPix.
- Faro é o nó CloudIFF de papel `edge`; seu perfil deseja `portal-host`, mas o cutover do Portal ocorre somente após onboarding Faro e portões de portal shadow.
- O onboarding Faro permanece aceito: 4 vCPU online, identidade própria, PKI/NATS individual, agent não-root, heartbeat direto para Hospedagem, reconciliação/resiliência e rollback possuem evidência mecânica.
- O heartbeat Faro observa `inventory`, `health`, `telemetry-host`, `portal-host` e `agent-auto-update`; `build` e `runtime` continuam excluídas do perfil Faro.
- Releases de agent-skills permanecem imutáveis; o runtime Faro continua na release instalada `cloudiff@0.1.4`, enquanto a skill de projeto observada no repositório é `cloudiff@0.1.5`.

## Decisões superadas
- Interpretar `FrozenPortalInterface` como congelamento da interface do GRUPix — superado pela decisão humana de 03/09/2026; o congelamento é exclusivo do Portal CloudIF.
- Faro bloqueado por `2/4 vCPU` — superado em 26/08/2026 após ampliação da VM e observação de CPUs `0-3`.
- `portal-host` apenas desejada/não observada — superado pelo heartbeat PostgreSQL que anunciou `portal-host`; isso não equivale a cutover do Portal.

## Decisões humanas pendentes
- Nenhuma decisão humana adicional para a U46; o operador autorizou corrigir backend/configuração do CloudIF e usar o GRUPix como canário, preservando a UI CloudIF congelada.
- Cutover definitivo do Portal para Faro permanece unidade posterior e não foi executado implicitamente.

## Decisões fechadas nesta emenda
- Escopo do congelamento visual esclarecido: CloudIF congelado; GRUPix modificável em seu próprio projeto.

## Pendências técnicas não humanas
- U46: a release ativa do BuildBroker e o `main` diferiam apenas no default do Artifact Executor; o default incorreto era `http://10.62.91.3`, enquanto o executor real foi observado em `10.62.91.2:18216`.
- U46: o unit do BuildBroker permitia apenas `127.0.0.0/8`; a correção local inclui `IPAddressAllow=10.62.91.2/32`.
- U46: `/etc/cloudif/build-broker.env` observado em Hospedagem ainda aponta para `http://10.62.91.3`; promoção operacional está bloqueada até retorno da rede e smoke do candidato.
- Segmento Work/campus `10.62.*` indisponível desde a execução da candidata: peers do MikroTik `10.20.0.4` e do túnel legado `wg0` deixaram de renovar handshake; `10.62.92.7`, `.91.2`, `.91.3` e `.91.5` ficaram inacessíveis por todos os saltos testados.
- `desenvolvedor-de-software` está fixado em `14` em `competencias.yaml`, enquanto a versão remota carregada nesta unidade foi `15`; reconciliar a referência na próxima alternância de unidade, sem normalização silenciosa.
- Permanecem entradas pendentes/preexistentes fora da U46 conforme contrato v45; nenhuma foi promovida por associação.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade U46 ativa, zona restrita ao BuildBroker, seu unit/teste/config de exemplo, `manifesto.yaml` e `estado.md`; nenhum arquivo da interface CloudIF está reservado ou alterado.

## Competências ativas nesta unidade
- `cloudiff@0.1.5` — skill raiz observada no repositório.
- `desenvolvedor-de-software@15` — método remoto carregado para a U46; divergência com a referência local `14` registrada acima.
- `github-incremental-reconciliation@7` — reconciliação incremental antes de normalização/release.
- `telemetry-data-visualization@2` — macro global; coletor específico de telemetria de sessão não foi localizado no repositório, portanto contagens de tokens/custo permanecem `indisponivel`.
- `cloudiff-safe-release@1.0.0` — candidato isolado e rollback obrigatório antes da promoção.
- `platform-engineering` — rota, systemd, allowlist e smoke multi-host.

## Falhas de portão por tipo de entrada
- `backend-integracao/BuildBroker`: canário GRUPix `build_6693a7e361362a241e1689fc` falhou após retries; causa primária reconciliada para endpoint errado do Artifact Executor.
- `infraestrutura/BuildBroker`: teste vermelho provou ausência de `IPAddressAllow=10.62.91.2/32` no unit.
- `rede`: recuperação do `wg0` foi tentada e o túnel permaneceu sem handshake; peers MikroTik em IPsec/WireGuard/LabIF também ficaram stale, bloqueando o smoke remoto.

## Divergências da última reconciliação
### Corrigidas localmente, ainda não homologadas no runtime
- `cloudif-build-broker.py`: default do Artifact Executor alterado para `http://10.62.91.2:18216`.
- `cloudif-build-broker.service`: allowlist inclui `10.62.91.2/32` além do loopback.
- `config/control-plane/build-broker.env.example`: endpoint não secreto atualizado para o executor real.
- `test_multiservice_build_broker.py`: regressões para endpoint e allowlist adicionadas; suíte específica 9/9 PASS; `git diff --check` PASS.

### Pendentes por capacidade/rede
- Aplicar correção no `/etc/cloudif/build-broker.env`, promover release candidata, reiniciar somente `cloudif-build-broker.service` e executar canário GRUPix.
- Validar se o Artifact Executor consegue falar com o Forja Agent local; só corrigir a suspeita `127.0.0.1:18095` se o canário reproduzir essa falha.
- Preview, homologação e conciliação do GRUPix permanecem bloqueados até o build real passar.

## Entradas em curso nesta unidade
- 367 `components/control-plane/current-apps/build-broker-current/cloudif-build-broker.py`.
- 471 `components/control-plane/etc/systemd/system/cloudif-build-broker.service`.
- 1004 `config/control-plane/build-broker.env.example`.
- 1215 `portal/tests/test_multiservice_build_broker.py` — teste de backend/infra; nenhum código de interface foi alterado.

## Portões U46
- `U46_RED_ENDPOINT_GATE=PASS`: teste reproduziu `10.62.91.3 != 10.62.91.2:18216` antes da correção.
- `U46_RED_NETWORK_GATE=PASS`: teste reproduziu ausência de allowlist da Forja antes da correção.
- `U46_UNIT_TESTS=PASS`: 9/9 testes do BuildBroker.
- `U46_DIFF_CHECK=PASS`.
- `U46_RUNTIME_SMOKE=PENDENTE_REDE`.
- `FROZEN_CLOUDIF_UI=PASS`: nenhum arquivo de UI/Portal foi modificado.

## Próxima unidade
- Retomar a mesma U46 quando o segmento `10.62` responder: validar estado da candidata criada parcialmente, executar/recuperar rollback se necessário, promover atomicamente a correção e repetir build → preview do GRUPix.
- Somente após U46 aceita, abrir unidade própria no GRUPix para adaptar checkout/estoque, notificação PagTesouro e interface de venda.
