# Estado — 2026-08-24 — contrato v39

## Decisões vigentes
- CloudIFF é um único projeto: V1/Python e V2/C++23 são reconciliados incrementalmente antes de qualquer normalização ou remoção.
- A skill raiz única é `cloudiff@0.1.1`; o próprio repositório CloudIFF é a fonte da skill e o catálogo PGH apenas registra/relaciona.
- `FrozenPortalInterface` é o requisito mestre: implementação pode mudar, mas a interface gráfica homologada, navegação, rotas e comportamento visível não mudam sem decisão humana explícita separada.
- Migração tecnológica segue strangler/coexistência: candidata, paridade, canary, observação, cutover e rollback preservado.
- Faro é alvo efetivo durante a conciliação sempre que uma entrada elegível exigir deploy nele; não se espera o fim de toda a migração para testar o host real.
- OpenCode ou outro agente auxiliar não é instalado em servidor/container sem autorização explícita.

## Decisões superadas
- Tratar os 1.320 arquivos V1 como `preexistente` não auditado — superado pela auditoria integral 1.320/1.320 e pela promoção mecânica desta emenda.
- Tratar a cópia de skill no catálogo como segunda autoridade — superado: `skills/cloudiff/SKILL.md` é a fonte única e o catálogo aponta para ela.
- Estado operacional que descrevia o filesystem do control-plane em 100% — superado pela expansão online do disco/LVM/ext4 nesta unidade.

## Decisões humanas pendentes
- Nenhuma decisão humana nova bloqueia a v39; o bloqueio restante é técnico/ontológico e será tratado na v40.

## Pendências técnicas não humanas
- `RECONCILIATION_CLOSURE` da skill de projeto está bloqueado por 8 referências ainda `preexistente`: seis externas com procedência recuperável e duas skills CloudIFF locais sem fonte compartilhada. v39 não é release para Faro.
- Cinco arquivos V1 permanecem `preexistente` porque o portão de links Markdown encontrou referências quebradas: uma referência transitória na skill Playwright vendorizada e quatro links Logflare sem esquema em templates Supabase.
- A suíte oficial passa 1.008 testes com 1 skip, mas emite `ResourceWarning` de handles/sockets não fechados no teardown; registrar e corrigir em unidade própria se persistir.
- Heartbeat remoto de dois nós de execução permanece stale desde 22/08 após indisponibilidade NATS; v36 de reconnect/readiness continua aberta e precisa de outage real sem restart do agente para aceite.
- Sete entradas permanecem declaradas e ainda não geradas: LegacyRetirement, monitoramento padrão e teste de perfil Faro.
- Backup remoto principal continua sem integridade completa enquanto o servidor de backup estiver fora da rede; remoção destrutiva de legacy segue bloqueada.

## Trabalho compartilhado
- `manifesto.yaml.trabalho_compartilhado` — unidade `normalize-v1-namespace-v39`, estado `concluido`, sem zona de exclusão ativa.

## Competências ativas nesta unidade
- `cloudiff@0.1.1` — skill raiz do projeto.
- `desenvolvedor-de-software@14` — método de trabalho de projeto.
- `github-incremental-reconciliation@7` — reconciliação antes da normalização.
- `governanca-ontologica-de-skills@1.0.4` — fecho/identidade da skill e referências.
- `telemetry-data-visualization@2` — macro obrigatória; início registrado no journal com plano congelado.
- `ddia-systems@1.4.0` — gate de schema/migrations SQL em database efêmero.

## Falhas de portão por tipo de entrada
- `documentacao-estrutural`: 5 arquivos V1 reprovaram integridade de link Markdown e permanecem `preexistente`.
- `ui-compat`: `pytest` não existe em Forja e não foi instalado por conveniência; os mesmos testes foram executados pelo runner `unittest` já disponível e passaram 6/6.
- `dados`: duas tentativas iniciais de gate SQL falharam antes de criar database de teste (PostgreSQL indisponível por disco cheio; depois formato/transferência temporária). Após a recuperação do host, database efêmero isolado passou 3 migrations + 3 testes.
- `infraestrutura`: PostgreSQL entrou em restart loop porque o filesystem raiz estava em 100%; a causa foi capacidade virtual já entregue mas partição/LVM/ext4 ainda não expandidos.

## Divergências da última reconciliação
### Corrigidas
- Os 1.320 arquivos não declarados eram exatamente os 1.320 arquivos auditados; todos foram declarados no namespace v39.
- 1.315/1.320 arquivos V1 passaram o portão declarado e foram promovidos para `aceito`; 5 permaneceram `preexistente` por discordância real.
- Seis SQL previamente `aceito` existiam no runtime V2, mas eram omitidos pelo `*.sql` global do `.gitignore`; foram recuperados byte a byte pelos hashes operacionais e apenas esses seis caminhos ganharam exceção de source-control.
- O gate SQL efêmero passou: 3 migrations, 3 testes, schema versão 1 e 11 tabelas; database temporário removido ao final.
- Filesystem do control-plane: disco virtual passou a 200 GiB; partição/PV/LV/ext4 foram expandidos online. O root ficou em ~195 GiB, ~20% usado e ~150 GiB livres, sem apagar arquivos.
- PostgreSQL concluiu crash recovery e voltou a aceitar conexões. `control`, `worker` e `agent` foram recuperados em ordem e estão ativos, sem reinícios novos ou warnings recentes.
- Aceites v38 observados no checkout concorrente foram preservados semanticamente nesta emenda; nenhuma alteração concorrente foi descartada.

### Pendentes de autorização ou unidade própria
- Corrigir conteúdo das cinco referências Markdown quebradas.
- Fechar v36 de reconexão NATS/readiness com teste real de indisponibilidade sem restart dos agentes.
- Implementar as sete entradas ainda pendentes quando suas dependências forem elegíveis.

## Entradas aceitas nesta unidade
- Estrutura v39: `manifesto.yaml`, `competencias.yaml`, `tools/verify_namespace.py`, `tests/test_v1_namespace_audit.py` e evidências de reconciliação associadas.
- V1 auditado: 1.315 arquivos promovidos a `aceito`; 5 mantidos `preexistente` por falha de link.
- SQL recuperado: `001_bootstrap`, `002_job_engine`, `003_job_kind_filter` e três testes SQL, com hashes preservados.
- Aceites v38 concorrentes preservados: léxico, preparação Faro, AgentUpdate, AdminObservability patch/test e skill/reconciliação v38.

## Próxima unidade
- v40: fechar a ontologia da skill `cloudiff` — verificar fontes/commits dos externos, internalizar as duas skills CloudIFF locais como `compoe`, incrementar/recarregar a skill e obter `RECONCILIATION_CLOSURE=PASS`/`DEPENDENCY_REFERENCES=PASS`.
- Depois, fechar v36 de reconnect/readiness porque heartbeat confiável é pré-condição para o onboarding real do Faro; em seguida reconciliar perfil/reserva e implementar nele os serviços elegíveis, preservando a interface atual.
