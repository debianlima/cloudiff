# Estado — 2026-08-26 — contrato v45

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a v45 não altera Portal/UI, navegação, rotas de usuário ou comportamento visual homologado.
- Releases de agent-skills são imutáveis: o sincronizador sempre prova o TAR recebido contra `NEW_MANIFEST`, mesmo quando o target já existe; membros especiais de arquivo são rejeitados; `current`/`previous` precisam ser symlinks antes de mutação.
- A v45 homologa a sincronização de agent-skills sem instalar OpenCode, cliente ou agente adicional e sem promover uma release diferente quando o target atual já é equivalente.
- Faro tem alvo contratual humano de 4 vCPU; o último estado observado nesta unidade continua 2 vCPU (`CPU_ONLINE=0-1`). Workloads que exigem 4 vCPU permanecem bloqueados até 4 serem observadas no runtime.
- A skill ativa durante a unidade foi `cloudiff@0.1.4`. A homologação produziu `cloudiff@0.1.5` com L014; a nova versão ativa somente na próxima unidade.

## Decisões superadas
- Confiar apenas na árvore de uma release já existente como prova do artefato recebido — superado: o TAR recebido agora é validado sempre contra `NEW_MANIFEST`.
- Permitir symlink/hardlink/FIFO no TAR desde que não escapasse do path — superado: somente diretórios e arquivos regulares entram na release declarada.
- Tratar `readlink -f current` como prova suficiente da atomicidade — superado: `current` e, quando presente, `previous` precisam ser symlinks antes da mutação.

## Decisões humanas pendentes
- Nenhuma nova decisão humana na v45. O aumento do Faro para 4 vCPU já foi decidido pelo operador e aguarda execução da TI.

## Decisões fechadas nesta emenda
- O sincronizador de agent-skills deve falhar fechado para arquivo recebido divergente, tipos especiais não declarados e ponteiros que perderam a natureza de symlink.

## Pendências técnicas não humanas
- Faro permanece observado em 2/4 vCPU até a TI alterar a VM; rerodar o gate de capacidade antes de qualquer workload que requeira 4 vCPU.
- Cinco arquivos V1 permanecem `preexistente` por links Markdown quebrados, herdado do estado anterior e fora do escopo da v45.
- LegacyRetirement continua separado desta unidade e depende dos próprios gates de backup/substituto antes de qualquer retirada destrutiva.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — unidade `agent-skills-sync-v45`, concluída, sem zona de exclusão ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.4` — skill raiz efetivamente carregada no início da unidade.
- `desenvolvedor-de-software@14` — método PGH.
- `github-incremental-reconciliation@7` — reconciliação antes de normalização/release.
- `governanca-ontologica-de-skills@1.0.4` — atualização da skill e registro de catálogo após homologação.
- `telemetry-data-visualization@2` — macro global da unidade.
- `network-ssh-operations@1` — primeiro salto obrigatório, caminho SSH e homologação distribuída.
- `release-it@1.4.0` — idempotência, release imutável e rollback.

## Competências instaladas/atualizadas para unidades futuras
- `cloudiff@0.1.5` — L014: release existente não dispensa prova do artefato recebido; tipos especiais são rejeitados e ponteiros são provados antes da mutação.

## Falhas de portão por tipo de entrada
- `deploy` entrada 176: TAR com FIFO/symlink/hardlink podia passar porque o manifesto enumerava apenas arquivos regulares; corrigido com rejeição de membros não regulares/diretórios.
- `deploy` entrada 176: quando a release-alvo já existia, o TAR recebido não era comparado ao `NEW_MANIFEST`; corrigido por `validate_archive_manifest` obrigatório.
- `deploy` entrada 176: `current` como diretório comum só falhava após criar artefatos de promoção; corrigido com pré-condição `current_not_symlink` antes de qualquer mutação.
- `higiene`: `tests/__pycache__` criado por um gate auxiliar fez `scripts/validate.sh` reprovar; o temporário criado nesta unidade foi removido e a validação limpa passou. Não era defeito do produto.

## Divergências da última reconciliação
### Corrigidas
- O worktree v45 preservou o staged do agente anterior e recebeu somente o delta de hardness comprovado.
- As 13 referências e duas composições da skill de projeto foram reconciliadas contra o catálogo atual; versões em `metadata.version` foram tratadas como formato canônico válido das skills internas.
- O catálogo registra `cloudiff@0.1.5` por ponteiro ao repositório dono, sem duplicar a skill; `controle/caminhos-canonicos.yaml` recebeu o hash derivado do índice atualizado.

### Pendentes de autorização ou capacidade
- Faro: capacidade observada ainda 2 vCPU para alvo humano de 4 vCPU; aguarda TI.

## Entradas aceitas nesta unidade
- 2 `competencias.yaml` — skill raiz atualizada para candidata 0.1.5.
- 176 `deploy/sync_agent_skills.sh` — sincronização fail-closed, idempotente e atômica homologada.
- 177 `tests/test_agent_skills_sync.py` — allowlist, release imutável, archive hardness, NOOP, rollback e pré-condições de symlink homologados.
- 179 `skills/cloudiff/SKILL.md` — candidata `cloudiff@0.1.5` com L014.
- 182 `tests/test_cloudiff_project_skill.py` — gate da skill 0.1.5/ontologia/anti-ciclo atualizado.

## Portões v45
- `AGENT_SKILLS_SYNC_OFFLINE=PASS` com dry-run, atomicidade, NOOP, rollback, divergência, allowlist e proibição de instalação de agente.
- Hardness: TAR divergente em target existente rejeitado; FIFO/symlink/hardlink rejeitados; `current` não-symlink falha antes de efeitos colaterais.
- Mesmo SHA do sincronizador `e8e6528af7fed0920d0af28fe2ff7b5c335bce55be3116b7b665c916c4b4483b` em Forja, Hospedagem, Maurício, Faro e Pelego.
- Cinco hosts: `DRY_RUN_PASS -> NOOP -> POINTER_STABLE=PASS`; release permaneceu `cloudiff-project-0.1.4-20260825`, 27 skills; nenhuma promoção real.
- Suíte oficial: 1008 testes PASS + 1 skip.
- Frozen UI: 3/3 PASS; nenhum arquivo Portal/UI alterado.
- `CLOUDIFF_PROJECT_SKILL=PASS version=0.1.5 compoe=2 referencia=13 anti_cycle=PASS`.
- `DELTA_INVENTORY=PASS`; `LEARNING_PRESERVED=PASS`; `RECONCILIATION_CLOSURE=PASS`; `DEPENDENCY_REFERENCES=PASS`.
- Catálogo: `CATALOGO_SKILLS=PASS`; `SYNC_GUARD=PASS`; ponteiro `cloudiff@0.1.5` validado.
- Secret scan e `git diff --check`: PASS nos deltas da unidade.

## Próxima unidade
- Recarregar `cloudiff@0.1.5` antes de selecionar qualquer nova entrada.
- Reobservar o Faro antes de qualquer unidade que requeira 4 vCPU.
- Escolher a próxima entrada elegível fora de Portal/LegacyRetirement enquanto a capacidade do Faro ou gates destrutivos continuarem bloqueados.
