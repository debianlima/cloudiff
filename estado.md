# Estado — 2026-09-01 — contrato v73

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a correção desta unidade não altera HTML, CSS, JS visual, textos, botões ou layout.
- O link congelado `Visão geral` (`?tab=resumo`) deve produzir o mesmo painel acadêmico canônico servido na raiz do Portal; o renderer administrativo legado não é contrato visual válido para esse alias.
- A promoção produtiva da correção `Visão geral` está homologada: live hash `1ae42e1e...`, `current` no candidato, `previous` no baseline `4407bd7c...`, raiz/alias/navigation equivalentes e verificador residente `errors=0`.
- Faro é o nó CloudIFF de papel `edge`; seu perfil deseja `portal-host`, mas o cutover do Portal ocorre somente após onboarding Faro e portões de portal shadow.
- O onboarding Faro está aceito: 4 vCPU online, identidade própria, PKI/NATS individual, agent não-root, heartbeat direto para Hospedagem, reconciliação/resiliência e rollback já possuem evidência mecânica.
- O heartbeat atual do Faro observa capabilities `inventory`, `health`, `telemetry-host`, `portal-host` e `agent-auto-update`; `build` e `runtime` continuam excluídas do perfil Faro.
- O caminho crítico Faro é `10.62.91.5 -> NATS 10.62.92.7:14222 -> cloudiff-control -> PostgreSQL`; Forja e Maurício não participam do heartbeat crítico.
- Releases de agent-skills permanecem imutáveis; o runtime Faro continua na release instalada `cloudiff@0.1.4`, enquanto a skill de projeto usada nesta unidade é `cloudiff@0.1.27`.

## Decisões superadas
- Salto obrigatório via `172.16.0.1` para acessar máquinas do laboratório — superado em 28/08/2026 pela nova orientação da TI comunicada pelo operador; acesso operacional passa a ser direto pelo conector Labiff, mantendo pfSense/MikroTik apenas como equipamentos de rede quando necessário.
- Faro bloqueado por `2/4 vCPU` — superado em 26/08/2026 após a TI ampliar a VM e o SO observar CPUs `0-3`.
- `portal-host` apenas desejada/não observada — superado pelo heartbeat PostgreSQL atual, que já anuncia `portal-host`; isso não equivale a cutover do Portal.
- Confiar apenas na árvore de uma release de skills já existente como prova do artefato recebido — superado na v45 pelo gate do TAR recebido.

## Decisões humanas pendentes
- T-034R — hardening durável e eventual rotação do `NPM data/keys.json` alteram permissão/credencial e podem invalidar sessões; exigem autorização humana.
- T-036R — substituir marcadores frágeis do UI security gate por invariantes semânticos muda critério de aceite; exige decisão humana antes de correção/deploy.
- T-029R — implantação HA pfSense permanece humana por envolver VM/firewall/roteamento, inventário de IPs e WAN/TI.
- Cutover definitivo do Portal para Faro permanece unidade humana posterior e deve respeitar portal shadow/FrozenPortalInterface.

## Decisões fechadas nesta emenda
- T-033 permaneceu homologada no contrato v71; a retomada confirmou evidência SQLite 7/7 e testes semânticos já presentes no HEAD remoto, sem reabrir seu working tree antigo.
- T-035 homologou a correção estática do warning HTTP/2 NPM: `listen 443 ssl http2`/IPv6 foram substituídos por `listen ... ssl` + `http2 on` somente no bloco HTTPS de `admin.cloudiff.duckdns.org`.
- Nginx 1.25.1 é a origem normativa do warning: o parâmetro `http2` de `listen` é deprecated e a diretiva por servidor é a forma atual.
- O delta `desenvolvedor-de-software@14 -> @15` foi reconciliado como aditivo: `DELTA_INVENTORY=PASS`, `LEARNING_PRESERVED=PASS`, nenhuma regra CloudIFF substituída e referência avançada ao catálogo `047c1e9e...`.
- T-035 não alterou certificados, `server_name`, upstream, layout ou autoridade produtiva; `VISUAL_DIFF=NO` e nenhum reload/deploy live foi executado.
- Teste semântico: pretest direto falhou como esperado; após correção e endurecimento do helper, teste direto PASS e `pytest` 1/1 PASS em venv efêmero. Validator PASS, `diff --check` PASS e secret-shape scan PASS.
- Baseline pública read-only continuou HTTP/2 302 via OpenResty/Authenik; não é evidência de deploy da correção.
- O canal webdev não pôde receber evidência: link fixo 403 e link direto timeout; nenhum bypass de ACL foi tentado.

## Pendências técnicas não humanas
- T-033R BLOCKED: deploy do worker/client enriquecidos exige gate effectful separado e autorização adequada.
- T-028 BLOCKED: guest pfSense é KVM/QEMU e Proxmox VE é fortemente suportado por OUI/SMBIOS, porém o nó/cluster exato e o gatilho externo do boot 2026-08-28 13:12:48 -03 seguem `NAO_DECLARADO`; nenhum endpoint/log PVE autorizado existe no inventário atual.
- T-022/T-023/T-024/T-025/T-032 permanecem dependentes de wiring/releases externas.
- Reload/deploy da correção HTTP/2 NPM é gate effectful separado; T-035 termina sem executá-lo.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `T-037-pgh2-main-line-reconciliation`, ativa durante a reconciliação.

## Competências ativas nesta unidade
- `cloudiff@0.1.28` — skill raiz; T-037 reconcilia a linha homologada com `main` e a governança 1.0.5.
- `desenvolvedor-de-software@15` — método PGH, reconciliado antes da geração.
- `github-incremental-reconciliation@7` — reconciliação incremental.
- `governanca-ontologica-de-skills@1.0.5` — governança de candidatas/linhas, reconciliada antes da normalização.
- `telemetry-data-visualization@2` — macro global; coletor PGH de unidade indisponível.

## Falhas de portão por tipo de entrada
- `infraestrutura`: `pytest` não existia no host de perfil `registro`; teste foi primeiro executado diretamente pelo Python, depois repetido com `pytest 9.1.1` em venv efêmero.
- `infraestrutura`: helper inicial selecionava o bloco HTTP porque o mesmo `server_name` aparece duas vezes; corrigido para exigir `listen 443`.
- `infraestrutura`: primeira expectativa de upstream do teste era incorreta; substituída pelo upstream observado no contrato versionado, sem alterar a configuração para casar com o teste.
- `repository-validator`: `__pycache__` gerado pelo pytest efêmero foi removido antes do PASS.
- `observabilidade`: webdev fixo 403 e direto timeout; evidência externa não pôde ser alimentada.

## Divergências da última reconciliação
### Corrigidas
- T-037 inventariou `main=bc4effd53ecd80912ea2a3a4e4b6efb4852af4a9`, linha homologada pré-reconciliação `32c3900383e619cbacb12af87fb5a4149630d678` e merge-base `8cc669ae5fba38d7148192b295af632cbd1b9be7`: 33 commits de aprendizado no branch e 1 commit exclusivo de `main`.
- O commit exclusivo de `main` remove somente um bloco `trabalho_compartilhado` concluído; sua semântica é preservada no fechamento T-037, quando o bloco ativo volta a `{}`.
- `governanca-ontologica-de-skills` avançou 1.0.4 -> 1.0.5 após leitura do delta `a92f68b`: candidatas preservam `base_homologated_version` e usam `NEEDS_REBASE` quando a linha oficial avança; nenhuma aprendizagem CloudIFF foi removida.
- `desenvolvedor-de-software` avançou de 14 para 15 após leitura do único delta remoto (`50b43e3`); preservação integral confirmada.
- O único uso legado de `listen ... ssl http2` no `custom/http.conf` caiu de 2 para 0; `http2 on` ficou no bloco HTTPS.
- T-034R e T-036R foram reclassificados explicitamente como decisões humanas pendentes, não trabalho técnico executável.
- T-028 foi reconciliado com o inventário atual de dotfiles: Proxmox provável, nó/cluster ainda não identificados.

### Pendentes de autorização ou capacidade
- T-034R: autorização humana para hardening/rotação/restart do NPM.
- T-036R: decisão humana sobre nova semântica do UI security gate e posterior deploy/re-run.
- T-028: inventariar/fornecer endpoint do nó/cluster Proxmox que possui o UUID da VM pfSense; então ler task log, `qemu-server` e journal host-side de 13:05–13:15 -03.
- Webdev: restaurar caminho observável autorizado para alimentar `evidence/` sem contornar ACL.

## Entradas aceitas nesta unidade
- 823 `components/proxy/srv/cloudif/proxy/npm/data/nginx/custom/http.conf` — correção HTTP/2 estática.
- 1560 `tests/test_npm_http2_static_warning.py` — teste semântico 1/1 PASS.
- 1561 `docs/reconciliation/npm-http2-static-v72.json` — evidência T-035.
- 2 `competencias.yaml` — referência método @15.
- 179 `skills/cloudiff/SKILL.md` — referência método @15, skill permanece 0.1.27.
- 9 `estado.md` — snapshot v72.
- 10 `manifesto.yaml` — contrato v72 e zona liberada.

## Próxima unidade
- Nenhuma frente independente permanece READY no estado observado.
- Próximo gate técnico de T-028: obter/inventariar o endpoint Proxmox que possui o UUID da VM pfSense; sem isso o gatilho externo permanece `NAO_DECLARADO`.
- T-034R/T-036R/T-029R aguardam humano; T-022/T-023/T-024/T-025 dependem de sistemas/releases externos.
