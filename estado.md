# Estado — 2026-09-04 — contrato v46

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a homologação de concorrência não alterou layout, navegação nem rotas públicas visíveis.
- Releases e candidatos de Homologação/Produção permanecem imutáveis; Produção continua sujeita à autorização crítica humana já existente.
- O projeto `teste-sofa` permanece projeto descartável de QA operacional do owner `iff1742962`, com tenant `iff1742962-testesofa`, publicação estável 1010 e Preview W3 saudável.
- Homologação de operações de projeto inclui agora um portão explícito de concorrência com sessões independentes: `create+create`, `create+delete` e `delete+delete`, sempre com prova independente de isolamento de recursos.
- A skill de projeto vigente é `cloudiff@0.1.7`.

## Decisões superadas
- Considerar somente sequências de criação/exclusão suficientes para homologar o Portal — superado: a corrida real `create+delete` revelou lock SQLite que não aparecia em execução serial.
- Executar schema SQLite do Komodo a cada requisição sem coordenação de processo — superado por WAL, `busy_timeout`, `RLock` de schema e inicialização idempotente.
- Recuperar toda criação parcial diretamente de `initial-publication` — superado: quando o template não chegou a ser materializado, a recuperação deve retomar da etapa `template` usando metadados do job original.
- Tratar retry de provisionamento como prova suficiente de recuperação — superado: o retry comum preservava recursos, mas não reconstruía os marcadores de runtime ausentes antes da publicação inicial.

## Decisões humanas pendentes
- H001 Publicação P2 do `teste-sofa`: `deployment.production.activate` continua aguardando dois aprovadores humanos distintos com perfil `admin` ou `professor`; o owner `iff1742962` não possui `can_decide` e o executor não deve contornar esse gate.

## Decisões fechadas nesta emenda
- O portão de concorrência de projeto passou a exigir três quadrantes reais: dois creates simultâneos, create em paralelo com delete de outro projeto e dois deletes simultâneos.
- O banco SQLite de estado do Komodo foi tornado seguro para requisições concorrentes; após o deploy não houve novo `database is locked` durante os testes reais.
- A recuperação de criação parcial foi estendida para reconstruir a etapa de template quando os marcadores duráveis nunca chegaram a existir.
- O teste regressivo `portal/tests/test_komodo_sqlite_concurrency.py` foi incorporado ao namespace fechado como entrada 1515.
- As referências PGH da skill de projeto foram reconciliadas até o catálogo `5641d1172b1d6249cdc2770555de87c5a3e320c6`: `desenvolvedor-de-software@15` e `governanca-ontologica-de-skills@1.0.5`; referências sem delta de conteúdo foram avançadas após comparação mecânica.

## Pendências técnicas não humanas
- A concorrência de criação/exclusão de projetos está homologada tecnicamente nesta unidade.
- Os tenants de QA `iff1742962-teste4` e `iff1742962-teste5` foram preservados pela política normal de retenção do CloudIFF ao excluir os projetos; nenhum projeto, runtime, publicação ou repositório Forgejo correspondente permanece ativo.
- P2 do `teste-sofa` continua tecnicamente pronta apenas até o gate humano; após as duas aprovações resta `production/enqueue`, smoke de P2 e rollback real.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — vazio após o fechamento da U07; nenhuma zona de exclusão permanece reservada.

## Competências ativas nesta unidade
- `cloudiff@0.1.7` — skill raiz, atualizada com L016 e L017 após homologação real.
- `desenvolvedor-de-software@15` — método PGH vigente; delta de supersessão mínima lido e preservado.
- `github-incremental-reconciliation@7` — reconciliação incremental antes do fechamento estrutural.
- `governanca-ontologica-de-skills@1.0.5` — política vigente; delta de linhas homologadas/candidatas lido e não conflita com a unidade.
- `telemetry-data-visualization@2` — macro global obrigatória da unidade.

## Falhas de portão por tipo de entrada
- `runtime/concorrencia`: `create+delete` reprovou inicialmente com `sqlite3.OperationalError: database is locked` no Komodo Agent.
- `provisionamento/recuperacao`: a criação parcial de `teste-5` ficou sem `managed-runtime.json`/`template-applied.json`; retry comum não tinha etapa segura para concluir a publicação.
- `publicacao/producao`: sem falha técnica nova; permanece bloqueio humano deliberado de dupla aprovação para P2.

## Divergências da última reconciliação
### Corrigidas
- `teste-3` foi excluído com sucesso após o fix de concorrência enquanto `teste-5` ainda era provisionado.
- `teste-5` foi recuperado da etapa `template` até `status=succeeded`, publicação 1017 e HTTPS 200, sem recriar banco/repositório/projeto.
- `teste-4` e `teste-5` foram excluídos simultaneamente por duas sessões independentes: jobs `8dbcad734f7f4bb9bca102185ad86793` e `bcaae2af4b1840279e6c1a35ce3739dc`, ambos `succeeded`, com requisições sobrepostas e IDs distintos.
- Control Plane retornou 404 para `teste-4`/`teste-5`; Forgejo retornou 404 para ambos; o destroy do Komodo confirmou stack e repo ausentes; publicações 1015/1017 deixaram de possuir certificado/rota próprios.
- `teste-sofa` permaneceu intacto após as exclusões concorrentes: Control Plane 200, Forgejo 200, runtime `healthy=true`, `issues=[]`, terminal OK, Preview W3 saudável e `https://1010.cloudiff.duckdns.org/` HTTP 200/TLS válido.
- Não houve novo `database is locked` no Komodo após o deploy do fix durante os testes de exclusão concorrente.
- `portal/tests/test_komodo_sqlite_concurrency.py` foi declarado na entrada 1515; `versao_contrato` avançou de 45 para 46.
- Referências do catálogo da skill de projeto e de `competencias.yaml` foram reconciliadas até `5641d1172b1d6249cdc2770555de87c5a3e320c6`.

### Pendentes de autorização ou capacidade
- Aprovação crítica P2 de `teste-sofa` continua pendente de dois aprovadores humanos distintos admin/professor.
- Exclusão física dos tenants de QA preservados não faz parte da exclusão normal de projeto e não foi executada implicitamente.

## Entradas aceitas nesta unidade
- 849 — Komodo Agent runtime: concorrência SQLite homologada.
- 988 — cópia operacional versionada do Komodo Agent reconciliada com o mesmo fix.
- 658 — status de provisionamento: recuperação por metadados do job anterior.
- 659 — worker de provisionamento: retomada condicional a partir de `template`.
- 389 e 1116 — texto/fluxo de recuperação do Portal mantidos coerentes com a retomada por última etapa segura.
- 1515 — teste regressivo de concorrência SQLite do Komodo.
- `skills/cloudiff/SKILL.md` — L016/L017 e versão 0.1.7.
- `competencias.yaml` — versão e referências PGH reconciliadas.

## Portões da unidade
- `CONCURRENT_CREATE_34=PASS`: `teste-3` e `teste-4` criados em sessões independentes com janela de requisição sobreposta e recursos distintos.
- `CREATE5_DELETE3_CONCURRENCY=PASS_AFTER_FIX`: a primeira execução revelou o lock; após o fix, a exclusão de `teste-3` concluiu enquanto `teste-5` permanecia em provisionamento.
- `CONCURRENT_DELETE_45=PASS`: duas exclusões simultâneas, jobs distintos, ambas `succeeded`.
- `NO_CROSS_PROJECT_DELETE=PASS`: `teste-sofa` permaneceu saudável e publicamente acessível após as corridas.
- `KOMODO_SQLITE_CONCURRENCY=PASS`: 16 threads, 240 operações de leitura/escrita, sem lock.
- `PROJECT_RECOVERY=PASS`: `teste-5` retomado da etapa segura faltante até publicação 1017.
- `UNIT_TESTS=PASS`: 46/46 nos contratos de concorrência, recovery, delete, terminal e W/H/P.
- `PY_COMPILE=PASS`, `DIFF_CHECK=PASS`, `STRUCTURE_PARSE=PASS`.
- `DELTA_INVENTORY=PASS` e `LEARNING_PRESERVED=PASS`: deltas 14→15 do método e 1.0.4→1.0.5 da governança foram lidos; regras não conflitantes foram preservadas.

## Próxima unidade
- Após a dupla aprovação humana de P2, executar `production/enqueue`, validar P2/stable URL/artefato/terminal e realizar rollback real; a concorrência de CRUD de projetos não permanece como bloqueio técnico.
