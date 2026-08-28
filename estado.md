# Estado — 2026-08-28 — contrato v64

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a correção desta unidade não altera HTML, CSS, JS visual, textos, botões ou layout.
- O link congelado `Visão geral` (`?tab=resumo`) deve produzir o mesmo painel acadêmico canônico servido na raiz do Portal; o renderer administrativo legado não é contrato visual válido para esse alias.
- A promoção produtiva da correção `Visão geral` está homologada: live hash `1ae42e1e...`, `current` no candidato, `previous` no baseline `4407bd7c...`, raiz/alias/navigation equivalentes e verificador residente `errors=0`.
- Faro é o nó CloudIFF de papel `edge`; seu perfil deseja `portal-host`, mas o cutover do Portal ocorre somente após onboarding Faro e portões de portal shadow.
- O onboarding Faro está aceito: 4 vCPU online, identidade própria, PKI/NATS individual, agent não-root, heartbeat direto para Hospedagem, reconciliação/resiliência e rollback já possuem evidência mecânica.
- O heartbeat atual do Faro observa capabilities `inventory`, `health`, `telemetry-host`, `portal-host` e `agent-auto-update`; `build` e `runtime` continuam excluídas do perfil Faro.
- O caminho crítico Faro é `10.62.91.5 -> NATS 10.62.92.7:14222 -> cloudiff-control -> PostgreSQL`; Forja e Maurício não participam do heartbeat crítico.
- Releases de agent-skills permanecem imutáveis; o runtime Faro continua na release instalada `cloudiff@0.1.4`, enquanto a skill de projeto usada nesta unidade é `cloudiff@0.1.21`.

## Decisões superadas
- Salto obrigatório via `172.16.0.1` para acessar máquinas do laboratório — superado em 28/08/2026 pela nova orientação da TI comunicada pelo operador; acesso operacional passa a ser direto pelo conector Labiff, mantendo pfSense/MikroTik apenas como equipamentos de rede quando necessário.
- Faro bloqueado por `2/4 vCPU` — superado em 26/08/2026 após a TI ampliar a VM e o SO observar CPUs `0-3`.
- `portal-host` apenas desejada/não observada — superado pelo heartbeat PostgreSQL atual, que já anuncia `portal-host`; isso não equivale a cutover do Portal.
- Confiar apenas na árvore de uma release de skills já existente como prova do artefato recebido — superado na v45 pelo gate do TAR recebido.

## Decisões humanas pendentes
- Nenhuma decisão humana adicional para aceitar o nó Faro.
- Cutover definitivo do Portal para Faro permanece uma unidade posterior e deve respeitar os portões de portal shadow/FrozenPortalInterface; não foi executado implicitamente nesta unidade.

## Decisões fechadas nesta emenda
- O contrato/source do `AdminObservability` C++ define backend loopback 18260, GET de ambiente/policy e POST transacional de recovery policy; o patch Portal versionado usa exatamente 18260, Authentik group `CloudIF-Tenants-Admin` e CSRF existente.
- O caminho live não foi declarado aceito: durante T-021, Labiff manteve rota via wg0, mas 10.62.92.7/10.62.91.3/10.62.91.2 ficaram inalcançáveis; o endpoint público do Portal também expirou.
- Sem acesso ao consumidor live, não se infere que Portal→18260 esteja ativo agora, nem se executa POST de recovery para compensar ausência de prova GET.

## Pendências técnicas não humanas
- T-021 permanece pendente de gate live: observar unit/binário 18260, Portal autenticado GET `/api/admin-observability`, policy GET e ausência de mutação por leitura quando a rede CloudIFF voltar.
- O teste histórico `tests/test_portal_admin_observability.py` depende do executável `patch`, ausente no terminal WireGuard; essa limitação do executor não é evidência de falha do Portal.
- T-023 permanece bloqueada até release C++ nova com `release-manifest.json`.
- T-024 wiring futuro do mcp-upload continua dependente de mudança real no consumidor.
- T-014 política de retenção no 251 permanece READY.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `T-021-admin-observability-cpp-audit`, concluída com lacuna externa; nenhuma zona de exclusão permanece ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.21` — skill raiz; L030 homologado.
- `desenvolvedor-de-software@14` — método PGH.
- `github-incremental-reconciliation@7` — reconciliação incremental.
- `governanca-ontologica-de-skills@1.0.4` — governança da skill.
- `telemetry-data-visualization@2` — macro global; coletor indisponível.
- `platform-engineering` / `operational-ui-truth` — prova de rota, capability, provider, consumer e efeito separado.

## Falhas de portão por tipo de entrada
- `live`: hosts CloudIFF 10.62.92.7/10.62.91.3/10.62.91.2 ficaram inalcançáveis via Labiff apesar de rota wg0 presente; autoridade live do AdminObservability não foi inferida.
- `executor`: teste de patch histórico não roda neste terminal por ausência do binário `patch`; testes que não dependem dele continuam executáveis.

## Divergências da última reconciliação
### Corrigidas
- Entrada 1541 separa wiring estático comprovado de gate live bloqueado; a indisponibilidade de rede é registrada sem promover o C++ a autoridade observada.
- Entrada 1542 impede overclaim enquanto `live_gate_passed=false`.
- Nenhum HTML/CSS/JS visual foi alterado (`VISUAL_DIFF=NO`).

### Pendentes de autorização ou capacidade
- Reexecutar somente os GETs live quando a rede retornar; POST `/node-recovery` não faz parte da auditoria read-only.
- O `main` do CloudIFF continua separado do branch auditável.

## Entradas aceitas nesta unidade
- Nenhuma nova entrada foi aceita em T-021; 1541/1542 permanecem `pendente` até o gate live.
- 9 `estado.md` — snapshot v64 registra a lacuna externa sem alterar `cloudiff@0.1.21`.
- 10 `manifesto.yaml` — contrato v64, entradas pendentes e zona liberada.

## Próxima unidade
- T-024: verificar se surgiu wiring real do `mcp-upload` C++ no consumidor; se não, registrar bloqueio por dependência sem inventar ligação.
- T-014 segue READY e independente.
