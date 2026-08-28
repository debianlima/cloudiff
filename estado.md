# Estado — 2026-08-28 — contrato v65

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
- T-024 não possui candidato técnico: 30 branches remotas foram inspecionadas e nenhuma versão do MCP Gateway contém `18234`, `CLOUDIFF_MCP_UPLOAD`, `mcp-upload` ou `mcp_upload` como wiring do consumidor.
- Commits posteriores a T-019 que tocaram áreas próximas pertencem a Faro/manifesto e não introduzem consumo do planner. O restart da release 0.20 permanece insuficiente para declarar integração.

## Pendências técnicas não humanas
- T-024 permanece bloqueada até surgir commit/branch com wiring explícito Gateway→planner e rollback/efeitos definidos; 1543/1544 permanecem `pendente`.
- T-021 permanece pendente de gate live enquanto a rede CloudIFF 10.62.* estiver indisponível via Labiff.
- T-023 permanece bloqueada até release C++ nova com `release-manifest.json`.
- T-014 política de retenção no 251 está READY e independente da rede 10.62.*.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `T-024-mcp-upload-wiring`, concluída com lacuna externa; nenhuma zona de exclusão permanece ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.21` — skill raiz; L030 homologado.
- `desenvolvedor-de-software@14` — método PGH.
- `github-incremental-reconciliation@7` — reconciliação incremental.
- `governanca-ontologica-de-skills@1.0.4` — governança da skill.
- `telemetry-data-visualization@2` — macro global; coletor indisponível.
- `platform-engineering` / `operational-ui-truth` — prova de rota, capability, provider, consumer e efeito separado.

## Falhas de portão por tipo de entrada
- `consumer-wiring`: nenhuma branch remota possui referência do MCP Gateway ao planner C++ 18234; T-024 não é executável sem artefato de migração.
- `live`: a rede 10.62.* segue indisponível pelo caminho autorizado Labiff, mantendo T-021 bloqueada.

## Divergências da última reconciliação
### Corrigidas
- Entrada 1543 registra busca agregada em 30 branches remotas e zero wiring do consumidor para o planner mcp-upload.
- Entrada 1544 transforma a ausência de candidato em gate mecânico contra ativação por inferência.
- Nenhum HTML/CSS/JS visual foi alterado (`VISUAL_DIFF=NO`).

### Pendentes de autorização ou capacidade
- A unidade só reabre quando o fluxo de migração publicar wiring explícito; nenhuma integração foi criada por este agente.

## Entradas aceitas nesta unidade
- Nenhuma nova entrada aceita; 1543/1544 permanecem `pendente` por ausência do candidato.
- 9 `estado.md` — snapshot v65.
- 10 `manifesto.yaml` — contrato v65 e zona liberada.

## Próxima unidade
- T-014: formalizar política de retenção no 251, independente da indisponibilidade 10.62.*.
- T-021 deve ser retomada quando a rede CloudIFF voltar para completar o gate live.
