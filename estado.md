# Estado — 2026-09-04 — contrato v46

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; nenhuma correção desta unidade alterou layout, navegação ou contrato visual congelado.
- `teste-sofa` continua projeto descartável de QA do owner `iff1742962`, tenant `iff1742962-testesofa`, publicação estável 1010, Preview W3 e candidato H2 homologado.
- Produção continua reutilizando exatamente o artefato homologado e exige autorização crítica humana antes de P2.
- A autorização `deployment.production.activate` do owner exige dois aprovadores humanos distintos com papel admin/professor; o executor não pode fabricar, impersonar ou contornar essas decisões.
- A skill de projeto vigente passa a `cloudiff@0.1.8`.

## Decisões superadas
- Reutilizar indefinidamente uma `production_activation_request` local `pending` sem reconciliar o status real da autorização — superado: autorização remota terminal (`expired`, `rejected`, `cancelled`) precisa ser renovada.
- Consumir um novo número P ao renovar somente o gate humano — descartado: renovação mantém o mesmo `publicationNumber` porque nenhuma release foi publicada.

## Decisões humanas pendentes
- H001 P2 do `teste-sofa`: autorização crítica `apr_b1953de4032c4211a8df` está `pending`, política `dual_admin_or_professor`, sem primeiro/segundo aprovador; o owner `iff1742962` possui `can_decide=false`.

## Decisões fechadas nesta emenda
- Autorização P expirada/rejeitada/cancelada é renovável pelo endpoint oficial sem alterar candidato nem consumir o próximo número de publicação.
- Estados ativos de autorização (`pending`, `pending_second`, `approved`, `reserved`) continuam idempotentes e não geram duplicata.
- O gate de Produção continua fail-closed: mesmo após a renovação correta, `production/enqueue` retorna 403 enquanto a dupla aprovação não tiver sido concluída.

## Pendências técnicas não humanas
- Nenhuma pendência técnica nova foi encontrada no Teste Sofá após os smokes finais desta unidade.
- Assim que H001 for satisfeita, resta executar `production/enqueue` para P2, esperar convergência, validar stable URL/artefato/terminal e executar rollback real para a release anterior.
- Os tenants dos projetos temporários de concorrência `iff1742962-teste4` e `iff1742962-teste5` continuam preservados por política de retenção; os projetos correspondentes permanecem excluídos.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — vazio após o fechamento da U08; nenhuma zona de exclusão permanece reservada.

## Competências ativas nesta unidade
- `cloudiff@0.1.8` — skill raiz, com L018 derivado de falha e reteste reais.
- `desenvolvedor-de-software@15` — método vigente.
- `github-incremental-reconciliation@7` — reconciliação incremental antes do fechamento.
- `governanca-ontologica-de-skills@1.0.5` — política vigente.
- `telemetry-data-visualization@2` — macro global obrigatória.

## Falhas de portão por tipo de entrada
- `publicacao/producao`: `production/approval/request` retornava HTTP 200 `existing=true` para uma autorização P2 já `expired`, impedindo renovação do gate humano.

## Divergências da última reconciliação
### Corrigidas
- `production/approval/request` agora reconcilia o status remoto da autorização antes de decidir idempotência.
- A autorização expirada `apr_fa70eb475aba452d83da` foi substituída via API oficial por `apr_b1953de4032c4211a8df` sem consumir P3: candidato 2 continua destinado a P2.
- Reteste de renovação: HTTP 200, `renewed=true`, novo ID, `status=pending`, `publicationNumber=2`; repetição: HTTP 200, `existing=true`, mesmo ID.
- Reteste fail-closed: `production/enqueue` com a autorização nova ainda pendente retornou 403 controlado.
- Smoke final independente: Control Plane 200 para `teste-sofa`; Teste 3/4/5 404; Repair `healthy=true`, `issues=[]`, terminal OK; W3/H2/P1/alias HTTP 200 e TLS válido; backup de banco/aplicação `ready`; zero novos `database is locked` após o fix U07.

### Pendentes de autorização
- H001: duas aprovações humanas distintas admin/professor para P2.

## Entradas aceitas nesta unidade
- 987 — contrato W/H/P: renovação de aprovação crítica terminal e preservação do número P.
- `skills/cloudiff/SKILL.md` — L018 e versão 0.1.8.
- `competencias.yaml` — versão da skill de projeto 0.1.8.

## Portões da unidade
- `P2_APPROVAL_REFRESH_TESTS=PASS`: 20/20 testes de W/H/P e política de aprovação.
- `P2_APPROVAL_RENEWAL=PASS`: renovação real e repetição idempotente em Produção.
- `FRESH_P2_HUMAN_GATE=PASS`: 403 antes da dupla aprovação, sem bypass.
- `FINAL_TECHNICAL_SMOKE=PASS`: Teste Sofá saudável, HTTPS/TLS válidos, backup pronto, projetos temporários excluídos e Komodo sem novo lock.
- `PY_COMPILE=PASS`, `DIFF_CHECK=PASS`, `SECRET_SCAN=PASS`.

## Próxima unidade
- Quando H001 for satisfeita por duas pessoas autorizadas, executar P2, validar exatamente o artefato H2 em Produção e testar rollback real; até lá o bloqueio é humano deliberado, não técnico.
