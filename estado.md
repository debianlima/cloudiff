# Estado — 2026-09-03 — contrato v45

## Decisões vigentes
- `FrozenPortalInterface` permanece requisito mestre; a correção operacional de publicação não alterou layout, navegação nem rotas visíveis do Portal.
- Releases e candidatos de Homologação/Produção permanecem imutáveis; Produção reutiliza exatamente o artefato homologado e exige aprovação crítica conforme a política atual.
- O projeto CloudIFF `laboratorio-de-hardware` usa owner `iff1742962`, número público `1001` e repositório Forgejo importado do GitHub anonimizado `debianlima/Laboratario-de-Hardware-2025-web`.
- A origem acadêmica importada está no commit `e55d8455a79f841c6ab83eeed0fe43799144202d`; Preview W1 está sincronizado nesse HEAD.
- A skill de projeto vigente é `cloudiff@0.1.6`.

## Decisões superadas
- Aumentar somente o timeout HTTP do Portal para homologação — superado: o Komodo Agent consumia `build_timeout`, não `timeout`, e mantinha o Docker Build em 300 s.
- Tratar `Remote end closed connection without response` como indisponibilidade do Komodo — superado pela evidência: serviço sem restart/OOM e build cancelado exatamente no limite interno de 300 s.
- Considerar o registro do projeto no Portal suficiente para aceite — superado pelo fluxo atual de Preview W, H e P com health e HTTPS independentes.

## Decisões humanas pendentes
- H001 Publicação P2 do `laboratorio-de-hardware`: a ativação crítica `deployment.production.activate` exige duas decisões humanas distintas de perfil `admin` ou `professor`. A conta owner `iff1742962` não possui `can_decide` no painel de aprovações; o pedido está pendente e não pode ser legitimamente autoaprovado pelo executor.

## Decisões fechadas nesta emenda
- O contrato de timeout foi corrigido de ponta a ponta: Portal envia `build_timeout=900` e o Komodo aceita `build_timeout` com fallback compatível para `timeout`.
- O job H3 concluiu com sucesso após 9m20s de execução, provando que o limite anterior de 300 s era a causa operacional.
- H3 foi homologado pelo owner após HTTPS 200/TLS válido e health do container.

## Pendências técnicas não humanas
- Nenhuma pendência técnica em Preview W1 ou Homologação H3: ambos estão saudáveis, HTTPS 200 e terminais preparados.
- Produção permanece na publicação legada P1 até a aprovação humana crítica de P2; após duas aprovações, resta enfileirar `production/enqueue` e executar os smokes finais de P2.
- O tenant Supabase, MCP, ACL e demais smokes globais do pedido de substituição continuam como fechamento posterior à promoção P2.

## Trabalho compartilhado
- ponteiro: `manifesto.yaml.trabalho_compartilhado` — vazio após o fechamento técnico desta unidade; nenhuma zona de exclusão permanece reservada.

## Competências ativas nesta unidade
- `cloudiff@0.1.6` — skill raiz do projeto, atualizada com o aprendizado homologado L015.
- `desenvolvedor-de-software@15` — método PGH vigente.
- `github-incremental-reconciliation@7` — reconciliação incremental antes de release.
- `governanca-ontologica-de-skills@1.0.5` — política vigente de skill/ontologia.
- `telemetry-data-visualization@2` — macro global obrigatória.

## Falhas de portão por tipo de entrada
- `publicacao/homologacao`: H3 falhou repetidamente com fechamento remoto porque o Portal aumentava `timeout`, mas o build real continuava limitado por `build_timeout=300` no Komodo Agent.
- `publicacao/producao`: não há falha técnica observada; existe gate humano deliberado de dupla aprovação para `deployment.production.activate`.

## Divergências da última reconciliação
### Corrigidas
- Portal e Komodo Agent agora compartilham o mesmo contrato de timeout do build de homologação.
- Preview W1: `healthy=true`, Git `synced`, HEAD `e55d8455a79f841c6ab83eeed0fe43799144202d`.
- Homologação H3: job `succeeded`, container `cloudif-p1001-d3-web` saudável, HTTPS/TLS válidos e candidato homologado.
- Repair dashboard do projeto: `running`, `healthy=true`, `issues=[]`, `terminal_ok=true`.
- Terminais de Preview W1 e Homologação H3 foram preparados via API e retornaram `terminalReady=true`.

### Pendentes de autorização ou capacidade
- Aprovação crítica P2 pendente de dois aprovadores humanos com perfil admin/professor. Nenhum bypass técnico é autorizado pelo contrato.

## Entradas aceitas nesta unidade
- 987 — correção do contrato de timeout de homologação/publicação, testes e deploy operacional.
- `skills/cloudiff/SKILL.md` — L015 homologado e versão incrementada para 0.1.6.
- `competencias.yaml` — referência da skill de projeto reconciliada para 0.1.6.
- `estado.md` — snapshot operacional desta unidade.

## Portões da unidade
- `PUBLICATION_TIMEOUT_CONTRACT=PASS`: Portal envia `build_timeout`, Komodo consome `build_timeout`/fallback `timeout`.
- `UNIT_TESTS=PASS`: 21/21 nos contratos W/H/P e runtime de publicação.
- `PY_COMPILE=PASS`, `DIFF_CHECK=PASS`, `SECRET_SCAN=PASS`.
- `PREVIEW_W1=PASS`: HTTP 200/TLS válido, `healthy=true`, Git sincronizado no commit de origem.
- `HOMOLOGATION_H3=PASS`: job concluído, HTTPS 200/TLS válido, artefato imutável `sha256:e811d342288db5ba3e00583dc5eb15ee48fb223e967839a4602f11900792fcd0`, status `homologated`.
- `TERMINAL_W1_H3=PASS` e `REPAIR_DASHBOARD=PASS`.
- `PRODUCTION_P2=BLOCKED_HUMAN_APPROVAL`: solicitação válida criada; política exige dois aprovadores distintos admin/professor.

## Próxima unidade
- Após a dupla aprovação humana de P2, consultar novamente a autorização, enfileirar `production/enqueue`, validar P2/stable URL/artefato, executar smokes finais e fechar reconciliação global do `laboratorio-de-hardware`.
