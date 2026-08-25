# Estado — 2026-08-24 — contrato v40

## Decisões vigentes
- CloudIFF V1/Python e V2/C++23 são um único projeto e são reconciliados incrementalmente antes de normalização, migração ou remoção.
- `FrozenPortalInterface` continua sendo o requisito mestre: troca de implementação não autoriza redesign, mudança de navegação, rotas ou comportamento visível homologado.
- Skill raiz canônica passa a ser `cloudiff@0.1.2`; deve ser recarregada antes da próxima unidade.
- A ontologia da skill separa `compoe` de `referencia`: `cloudiff-authentik-oidc@1.0.0` e `cloudiff-safe-release@1.0.0` são competências do próprio projeto; treze referências externas/PGH têm fonte, versão e commit lido fixados.
- Symlink/release operacional de skills é execução, não fonte canônica. Procedência vem de repositório/path/commit/hash ou de skill composta no próprio projeto.
- Faro continua alvo efetivo durante a conciliação quando uma entrada elegível exigir deploy real; OpenCode/outro agente não é instalado sem autorização explícita.

## Decisões superadas
- `cloudiff@0.1.1` — substituída por `0.1.2` após fecho ontológico v40; continua preservada no histórico Git e nas releases anteriores.
- Oito competências `preexistente` com `repositorio/caminho: NAO DECLARADO` — substituídas por seis referências externas provadas e duas competências internas `compoe`.
- Usar `/srv/cloudif/agent-skills/current` como origem de uma competência — substituído por procedência imutável; `current` permanece apenas caminho operacional.
- Estado antigo da Hospedagem com `/` em 100% — superado pela expansão online do disco/LVM/ext4 para ~195 GiB de filesystem, com ~150 GiB livres no último gate.

## Decisões humanas pendentes
- Nenhuma decisão humana nova bloqueia a próxima unidade técnica.

## Pendências técnicas não humanas
- v36 continua aberta: Forja e Maurício precisam provar reconexão NATS/heartbeat após indisponibilidade sem restart do agente; `systemctl active` isoladamente não vale aceite.
- Cinco arquivos V1 permanecem `preexistente` por links Markdown quebrados identificados na auditoria integral.
- Sete entradas declaradas continuam não geradas: contrato/config/testes LegacyRetirement, instalador de monitoramento padrão e teste de perfil Faro.
- Backup principal `pre-v2-20260820` não pode ter integridade remota completa enquanto o servidor de backup permanecer fora da rede; remoção destrutiva de legacy segue bloqueada.
- A suíte oficial passa, mas ainda emite `ResourceWarning` de handles/sockets no teardown; dívida técnica independente.

## Trabalho compartilhado
- `manifesto.yaml.trabalho_compartilhado` — unidade `skill-closure-v40`, concluída, sem zona de exclusão ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.1` — versão congelada no início da unidade; produziu candidata `0.1.2`, que só ativa na próxima unidade.
- `desenvolvedor-de-software@14` — método de projeto.
- `github-incremental-reconciliation@7` — inventário/delta antes de normalizar.
- `governanca-ontologica-de-skills@1.0.4` — composição, referência, anti-ciclo e fecho.
- `telemetry-data-visualization@2` — macro global; `telemetria_inicio` registrada com hash do plano.

## Competências instaladas para unidades futuras
- `cloudiff-authentik-oidc@1.0.0` — composta pelo projeto; corpo do aprendizado operacional original preservado.
- `cloudiff-safe-release@1.0.0` — composta pelo projeto; corpo do aprendizado operacional original preservado.
- `cloudiff@0.1.2` — raiz a ser recarregada antes da próxima unidade.

## Falhas de portão por tipo de entrada
- `documentacao-estrutural`: `scripts/validate.sh` reprovou quando testes geraram `__pycache__`; execução final usa `PYTHONDONTWRITEBYTECODE=1` e validação pós-teste PASS.
- `ontologia`: primeiro fecho cruzado assumiu `status` explícito em todos os nós; o validador canônico define ausência como `aceito`. Portão corrigido para a mesma semântica e passou.
- `procedencia`: Playwright inicialmente foi procurado em `skills/playwright`; o commit fixado prova o caminho real `skills/.curated/playwright`, depois validado byte a byte.

## Divergências da última reconciliação
### Corrigidas
- Delta concorrente `e4193a52f0ba0ea803f02fe414fa8f98bf86de6a` (SGLang v17) foi preservado por merge sem force; o commit de fecho do catálogo passou a `998b6256ad7d5e6e43fa1e3477cd83e86bef2632`.
- Seis competências externas foram comparadas contra seus commits upstream; todos os arquivos-fonte relevantes presentes na release instalada têm paridade SHA-256.
- Duas competências CloudIFF sem upstream foram internalizadas no repositório como `compoe` sem perder o corpo original.
- Catálogo candidato `998b6256ad7d5e6e43fa1e3477cd83e86bef2632` passou `CATALOGO_SKILLS=PASS` e `SYNC_GUARD=PASS`, com 53 competências aceitas e zero pendentes.
- Skill raiz `cloudiff@0.1.2`: `compoe=2`, `referencia=13`, anti-ciclo PASS.
- `RECONCILIATION_CLOSURE=PASS` para 16 nós/15 arestas e `DEPENDENCY_REFERENCES=PASS` para 13 referências + 2 composições.
- Interface congelada permaneceu inalterada; suíte oficial continua 1.008 testes PASS e 1 skip.

### Pendentes de autorização ou unidade própria
- Corrigir os cinco links Markdown sem alterar conteúdo vendorizado/upstream por conveniência.
- Executar a v36 de reconnect/readiness antes de depender do heartbeat do Faro.
- LegacyRetirement permanece bloqueado por backup/substituição, não por decisão de interface.

## Entradas aceitas nesta unidade
- 2 `competencias.yaml` — raiz `0.1.2`, referências fixas e duas composições internas.
- 179 `skills/cloudiff/SKILL.md` — `cloudiff@0.1.2` com L011 e fecho ontológico.
- 182 `tests/test_cloudiff_project_skill.py` — identidade, hashes, composição, referências e anti-ciclo.
- 1505 `skills/cloudiff-authentik-oidc/SKILL.md` — competência interna `1.0.0`.
- 1506 `skills/cloudiff-safe-release/SKILL.md` — competência interna `1.0.0`.
- 1507 `docs/reconciliation/skill-closure-v40.json` — evidência do fecho.

## Próxima unidade
- Recarregar `cloudiff@0.1.2` e executar v36 reconnect/readiness: cliente NATS reconecta após outage real sem restart; control aguarda PostgreSQL no boot sem StartLimit. Após isso, reconciliar perfil/reserva com o Faro real e implementar nele os serviços elegíveis, sem alteração da interface gráfica.
