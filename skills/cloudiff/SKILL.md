---
name: cloudiff
versao: 0.1.28
description: Governa, reconcilia, normaliza e evolui a plataforma CloudIFF V1/Python→V2/C++23 preservando interface homologada,
  contratos, segurança, dados, observabilidade e rollback.
tipo_competencia: projeto
origem:
  projeto_de_origem: cloudiff
  derivacao: original
  commit_divergencia: NAO APLICAVEL
  plataforma:
  - linux
  - systemd
  - docker
  - cxx23
  - python
  - postgresql
  - nats
  pressupostos:
  - interface homologada e rotas públicas são contratos de compatibilidade
  - produção usa releases imutáveis e rollback
  - reconciliação incremental antecede normalização
escopo_comum: arquitetura, operação, portal, agentes, mensageria, release e migração tecnológica da CloudIFF
escopo_proprio: decisões, invariantes e armadilhas verificadas no projeto CloudIFF
compoe:
- id: cloudiff-authentik-oidc
  fonte: skills/cloudiff-authentik-oidc/SKILL.md
  versao_fixada: 1.0.0
  estado: reconciliado
- id: cloudiff-safe-release
  fonte: skills/cloudiff-safe-release/SKILL.md
  versao_fixada: 1.0.0
  estado: reconciliado
referencia:
- id: desenvolvedor-de-software
  fonte: debianlima/competencias-catalogo:metodo/desenvolvedor-de-software/SKILL.md
  versao_fixada: '15'
  delta_lido_ate: 598790074a359b7755fcc50908195476dd0a4d87
  estado: reconciliado
- id: github-incremental-reconciliation
  fonte: debianlima/competencias-catalogo:metodo/github-incremental-reconciliation/SKILL.md
  versao_fixada: '7'
  delta_lido_ate: 598790074a359b7755fcc50908195476dd0a4d87
  estado: reconciliado
- id: governanca-ontologica-de-skills
  fonte: debianlima/competencias-catalogo:metodo/governanca-ontologica-de-skills/SKILL.md
  versao_fixada: 1.0.5
  delta_lido_ate: 598790074a359b7755fcc50908195476dd0a4d87
  estado: reconciliado
- id: telemetry-data-visualization
  fonte: debianlima/competencias-catalogo:dominio/telemetry-data-visualization/SKILL.md
  versao_fixada: '2'
  delta_lido_ate: 598790074a359b7755fcc50908195476dd0a4d87
  estado: reconciliado
- id: distributed-agent-control
  fonte: debianlima/competencias-catalogo:dominio/distributed-agent-control/SKILL.md
  versao_fixada: '1'
  delta_lido_ate: 598790074a359b7755fcc50908195476dd0a4d87
  estado: reconciliado
- id: network-ssh-operations
  fonte: debianlima/competencias-catalogo:dominio/network-ssh-operations/SKILL.md
  versao_fixada: '1'
  delta_lido_ate: 598790074a359b7755fcc50908195476dd0a4d87
  estado: reconciliado
- id: operational-ui-truth
  fonte: debianlima/competencias-catalogo:dominio/operational-ui-truth/SKILL.md
  versao_fixada: '1'
  delta_lido_ate: 598790074a359b7755fcc50908195476dd0a4d87
  estado: reconciliado
- id: cloud-design-patterns
  fonte: github/awesome-copilot:skills/cloud-design-patterns/SKILL.md
  versao_fixada: git:318066d2213b510e89b500ed0d53506c54093ddc
  delta_lido_ate: 318066d2213b510e89b500ed0d53506c54093ddc
  estado: reconciliado
- id: ddia-systems
  fonte: wondelai/skills:ddia-systems/SKILL.md
  versao_fixada: 1.4.0
  delta_lido_ate: 6bac1534f9f256a56fc2b4dd0e70b9a692758966
  estado: reconciliado
- id: release-it
  fonte: wondelai/skills:release-it/SKILL.md
  versao_fixada: 1.4.0
  delta_lido_ate: 6bac1534f9f256a56fc2b4dd0e70b9a692758966
  estado: reconciliado
- id: platform-engineering
  fonte: magnus919/agent-skills:platform-engineering/SKILL.md
  versao_fixada: git:ed68466e04c9b5d33898ed5b503fb828f49c3e73
  delta_lido_ate: ed68466e04c9b5d33898ed5b503fb828f49c3e73
  estado: reconciliado
- id: playwright
  fonte: openai/skills:skills/.curated/playwright/SKILL.md
  versao_fixada: git:49f948faa9258a0c61caceaf225e179651397431
  delta_lido_ate: 49f948faa9258a0c61caceaf225e179651397431
  estado: reconciliado
- id: cpp-pro
  fonte: saeed-vayghan/gemini-agent-skills:.gemini/skills/cpp-pro/SKILL.md
  versao_fixada: git:34ca3ca1db04b092c5f86eba155c23e105fc933b
  delta_lido_ate: 34ca3ca1db04b092c5f86eba155c23e105fc933b
  estado: reconciliado
---

# CloudIFF — skill de projeto

## 1. Origem e problema

CloudIFF é uma plataforma distribuída com Portal, plano de controle, runtime, proxy/publicação, agentes, mensageria e integrações. O histórico V1 predominava em Python e o núcleo V2 introduziu C++23. Ambos pertencem ao mesmo projeto e devem ser reconciliados incrementalmente; linguagem de implementação não pode apagar comportamento homologado.

A unidade de verdade combina documentação hierárquica, manifesto/contratos, código, testes, Git e runtime observado. Esta é a única skill raiz do projeto; outras skills são composição, referência ou aprendizado preexistente, nunca uma segunda autoridade de projeto.

A auditoria inicial encontrou 1.320 arquivos rastreados no Git V1, enquanto documentação gerada anterior registrava 1.157; o V2 operacional existia fora de um checkout Git próprio. A reconciliação deve preservar ambos os deltas antes de regenerar documentação ou normalizar nomes.

## 2. Decisões e alternativas descartadas

### FrozenPortalInterface — requisito mestre

A interface gráfica conhecida pelos usuários **não muda durante a migração**. Visão geral, Publicações, Projetos e Bancos/tenants, seus textos, layout, navegação, estilos, rotas e fluxos visíveis homologados só mudam mediante autorização humana explícita separada.

Evidência canônica: `portal/FROZEN_SURFACES.md`, `portal/tests/test_frozen_surfaces_contract.py`, `docs/portal-v2/REAL-PAGE-PROOF.json` e `config/portal-quality-baseline.json`.

**Descartado:** redesenhar UI ao trocar backend. Motivo: elimina o oráculo de compatibilidade e mistura duas variáveis.

### V1 e V2 são um único projeto

A reconciliação é aditiva antes de ser redutiva. V1 fornece baseline funcional/visual e rollback; V2 fornece a direção tecnológica. O inventário inicial provou zero colisões de caminho, permitindo união aditiva antes da normalização sem sobrescrever V1.

**Descartado:** big-bang ou substituição V1→V2 em massa.

### C/C++ é troca de implementação, não de contrato

Serviços e lógica de produção Python são candidatos prioritários a C++23 quando contrato, efeitos, segurança, dados, rotas e observabilidade puderem ser provados equivalentes. Python não é removido apenas por linguagem. Testes, geradores e ferramentas ficam até existir gate equivalente.

O plano inicial classificou 444 arquivos Python: 123 serviços/runtime candidatos prioritários a C++, 249 componentes de compatibilidade do Portal, 68 bibliotecas candidatas e 4 itens de tooling/verificação preservados até substituição equivalente.

### Migração por coexistência/strangler

`docs/REQUIREMENTS.md` e `docs/GUIA-DE-MIGRACAO.md` determinam coexistência: rotas migram uma por vez e fallback permanece até os portões fecharem. A referência inventariada mede 31 rotas e 93 combinações rota × grupo para preservar decisões de acesso.

## 3. Algoritmos criados ou modificados

### Reconciliação incremental CloudIFF

**Entrada:** Git canônico, árvore operacional, manifesto/contratos, READMEs, testes e runtime.

**Procedimento:** inventariar → classificar diferenças → preservar união válida → resolver conflitos por evidência → `DELTA_INVENTORY=PASS` + `LEARNING_PRESERVED=PASS` → somente então normalizar → repetir gates → registrar estado.

**Saída:** árvore versionada única sem perda de aprendizado válido.

### Migração por rota/serviço

1. identificar contrato de entrada/saída, side effects, autorização e dependências;
2. criar candidata C++ sem mudar rota ou resposta visível;
3. testar método, permissões, CSRF/OIDC/tenant e dados;
4. comparar resposta/DOM/screenshot quando houver UI;
5. injetar falhas relevantes: timeout, duplicata, reconnect, stale/fencing;
6. promover por release imutável com rollback;
7. retirar legado somente após aceite e backup íntegro.

### Método obrigatório por unidade

1. carregar `desenvolvedor-de-software@15`;
2. verificar `trabalho_compartilhado`/zona de exclusão;
3. reconciliar com `github-incremental-reconciliation@7`;
4. emitir `DELTA_INVENTORY=PASS` e `LEARNING_PRESERVED=PASS`;
5. aplicar `governanca-ontologica-de-skills@1.0.5` quando tocar skill/catálogo/relação;
6. normalizar somente o estado conciliado;
7. executar portões mecânicos independentes;
8. quando a entrada elegível exigir Faro, implantar e provar no Faro real `10.62.91.5` durante a própria unidade;
9. atualizar esta skill somente após aprendizado homologado.

## 4. Formatos de pesquisa que funcionaram

- buscar primeiro `README`, `FROZEN_SURFACES`, `REQUIREMENTS`, `AUDIT`, `INVENTORY`, `COVERAGE`, `current-apps` e units;
- interpretar cada arquivo pelo README ancestral mais próximo antes de classificá-lo;
- comparar `git ls-files` com inventários/documentação gerada antes de regenerá-los;
- usar SHA-256 para distinguir mirror deliberado de duplicação candidata;
- confrontar fonte versionada, configuração e runtime observado; nenhum deles sozinho é suficiente;
- comparar baseline versionado com release `previous` e live quando um teste de patch aparentar regressão.

## 5. Recriar do zero

1. clone a revisão CloudIFF escolhida;
2. valide manifesto, contratos, skill e referências;
3. execute `scripts/validate.sh` e `scripts/test.sh` antes de modificar;
4. leia o README ancestral de cada subsistema;
5. inventarie hashes, units, rotas, serviços e runtime real;
6. resolva o menor fecho de competências;
7. construa C++23 com CMake/Ninja/Clang, warnings zero e sanitizers;
8. migre por strangler/canary e preserve rollback;
9. use Faro quando a unidade o exigir;
10. só retire legado após gates e backup verificável.

## 6. Modificar sem quebrar

- **Interface:** frozen surfaces + hash/DOM/screenshot/Playwright quando aplicável.
- **Rotas:** endereço, método e semântica permanecem enquanto a política não mudar por decisão separada.
- **Autorização:** candidata decide igual ao baseline; isolamento tenant/objeto é obrigatório.
- **CSRF/OIDC:** toda ação mantém proteção e identidade.
- **APIs:** não remover/renomear chaves públicas sem contrato versionado.
- **Dados:** PostgreSQL/schema/migração exigem constraints, integridade e rollback; linguagem não autoriza trocar modelo de dados.
- **Mensageria/agentes:** testar duplicate delivery, reconnect, stale, fencing, restart real e idempotência.
- **Release:** nunca editar release ativo como fonte; candidato imutável, smoke, current/previous e rollback.
- **LegacyRetirement:** só após backup verificável e substituto aceito.
- **Faro:** é alvo efetivo de implantação quando a entrada exigir; não instalar OpenCode/agentes auxiliares sem autorização.
- **Interface administrativa:** necessidade operacional não autoriza alterar a UI de usuário.

## 7. Armadilhas e aprendizado acumulado

### L001 — documentação hierárquica é contrato de auditoria
Todo arquivo deve ser interpretado pelo README ancestral mais próximo e confrontado com controles/código/runtime. Evita classificar por nome sem contexto.

### L002 — interface congelada prevalece sobre refatoração
Implementação pode mudar; superfície homologada não muda junto. Gate: frozen-surface tests + prova de página real.

### L003 — união V1+V2 deve provar aditividade
V1 1.320 arquivos auditados; V2 importado sem colisão de caminho; união validada com 1.008 testes e 10 hashes de UI preservados; commit `2e869b7a5216a33bfb88875b97d710392d325ed0`.

### L004 — teste live pode se tornar autorreferente depois do deploy
`portal-admin-observability.patch` parecia reverso porque o teste aplicava o patch no live já patchado. O baseline V1/`previous` produziu exatamente o hash da release live. Gate: patch offline sobre baseline + hash de equivalência.

### L005 — normalização YAML deve ser mecânica
`manifesto.yaml` continha scalars `proposito` com `: ` sem aspas. Citar 20 scalars preservou os 175 propósitos anteriores e permitiu parse completo.

### L006 — scanner não deve se autoacusar
Testes de ausência de chave continham literalmente o marcador de chave privada e acionavam o scanner. Construir o marcador em runtime preservou a asserção e zerou falsos positivos.

### L007 — duplicação exige contexto antes de remoção
A auditoria dos 1.320 encontrou 84 grupos SHA-256 duplicados, muitos em templates/mirrors deliberados. Hash igual não autoriza exclusão.

### L008 — saúde do control-plane é gate de capacidade
Hospedagem foi observada com `/` em 100% e 17 units failed. Migração pesada não começa sem capacidade/saúde suficiente.

### L009 — `systemctl active` não prova reconexão
Agente pode permanecer ativo e não voltar a publicar após indisponibilidade NATS. Gate: `last_seen`/heartbeat retomado sem restart do agente.

### L010 — release imutável não recebe chmod corretivo
`cpp-pro` foi observado root-only em release antiga. Correção deve nascer em nova release reconciliada, não por mutação local.
### L011 — `current` é execução, não procedência de skill
Na v40, oito competências apareciam como `preexistente` porque o catálogo apontava para `/srv/cloudif/agent-skills/current`. O fecho recuperou `SOURCES.json`/`MANIFEST.json`, confirmou repositório+commit+path e comparou os bytes instalados com o upstream. As duas skills sem upstream eram aprendizado específico do CloudIFF e foram internalizadas como `compoe`. Gate: entrada 179/182 em 2026-08-24, `SOURCE_HASH_PARITY=PASS`, `RECONCILIATION_CLOSURE=PASS` e `DEPENDENCY_REFERENCES=PASS`. Evita promover symlink mutável a fonte ou inventar upstream. Vale em Linux/Git quando a release traz metadados de procedência ou quando há evidência equivalente verificável.

### L012 — capability de certificado do servidor não vira trust bundle do agente
Na v42, a coleção `nats-server-cert` do SecureDistribution foi auditada e continha `fullchain.pem` **e** `privkey.pem`, com audience restrita ao host que opera o servidor NATS. Conceder essa capability ao Faro teria atravessado a fronteira de confiança e exposto a chave privada do servidor. Para agentes, o gate correto é mTLS com certificado cliente próprio + CA confiável do sistema + `expected hostname`; SecureDistribution continua server-side para material do servidor. Gate: Faro `10.62.91.5`, certificado cliente serial `100B`, heartbeat E2E, ACL NATS positiva/negativa, `NATS_NO_CLIENT_CERT_DENIED=PASS` e capability auditada sem audience Faro em 2026-08-25. Evita transformar distribuição segura do servidor em distribuição indevida de segredo para clientes.

### L013 — `apply` idempotente não reinicia runtime equivalente
Na v44, o portão de deploy da entrada 174 reprovou porque duas execuções consecutivas de `install_webdev_workspace.sh apply` recriavam o container Selenium: `container ID` e `StartedAt` mudavam mesmo sem alteração de compose, config ou unit. A correção passou a comparar release atual, compose, instalador, config e unit live; runtime equivalente executa apenas reconciliação de firewall + health e retorna `WEBDEV_WORKSPACE=NOOP`, sem `systemctl restart`. Gate homologado em 2026-08-25: duas aplicações consecutivas preservaram exatamente o mesmo container ID e `StartedAt`; rota HTTPS também passou rollback→reapply. Evita transformar instalação declarativa em reinício disruptivo e perder sessões de automação. Vale em Linux/systemd/Docker Compose quando a release é imutável e o health gate consegue provar equivalência operacional.


### L014 — release existente não dispensa prova do artefato recebido
Na v45, o sincronizador de skills inicialmente aceitava três estados que quebravam o contrato de release imutável: TAR com FIFO/symlink/hardlink não representado no manifesto; TAR divergente quando a release-alvo já existia; e `current` como diretório comum, que só falhava após criar artefatos de promoção. A correção passou a rejeitar todo membro que não seja arquivo regular/diretório, validar o TAR recebido contra `NEW_MANIFEST` independentemente da existência do alvo e exigir `current`/`previous` como symlinks antes de qualquer mutação. Gate homologado em 2026-08-26: `AGENT_SKILLS_SYNC_OFFLINE=PASS`; hardness dos três casos PASS; e o mesmo SHA `e8e6528af7fed0920d0af28fe2ff7b5c335bce55be3116b7b665c916c4b4483b` produziu `DRY_RUN_PASS -> NOOP -> POINTER_STABLE=PASS` em Forja, Hospedagem, Maurício, Faro e Pelego. Evita confundir idempotência com confiança cega no target existente e preserva a atomicidade do ponteiro. Vale em Linux quando releases são árvores imutáveis identificadas por manifesto e promovidas por symlink.
### L015 — ação de UI que persiste configuração exige prova no artefato canônico
Em 2026-08-27, a auditoria do controle congelado **“Testar e salvar”** do backup remoto encontrou um teste que apenas procurava strings no código e um POST que gravava um caminho literal duplicado, enquanto a leitura usava `BACKUP_REMOTE_ENV`. A entrada 1178 passou a executar a persistência em diretório temporário e observar o efeito fora da interface: bytes antes/depois, conteúdo final exato, modo `0600`, replace atômico e ausência de temporário residual. A entrada 649 passou a gravar pela mesma fonte canônica `BACKUP_REMOTE_ENV`. Gate: `portal.tests.test_backup_remote_global_config` + regressão completa do Portal (1009 testes) + `VISUAL_DIFF=NO`. Evita homologar toast/string como efeito real e evita divergência futura entre caminho de leitura e caminho de escrita. Vale em Linux/Python para ações do Portal que persistem configuração em arquivo; a implementação pode migrar para C++ desde que preserve o mesmo contrato observável.

### L016 — wrapper POST que delega deve preservar o corpo e a autorização deve casar com o controle visível
Em 2026-08-27, a entrada 1518 executou os controles congelados de disponibilidade de Bancos contra SQLite temporário e runner Docker fake. O portão encontrou duas divergências que testes por strings não capturavam: `do_POST_v21` consumia o corpo antes de delegar, fazendo `start/stop` chegarem ao handler anterior com `tenant` vazio e virarem o fallback `projeto`; e o wrapper final tratava `keepalive` como admin-only embora a UI e `CLOUDIF_MAX_STUDENT_KEEPALIVE_HOURS` declarem tempo temporário para aluno. A correção preserva os bytes do POST e restaura `rfile`/`Content-Length` antes da delegação, e restringe o guard administrativo somente a `always_on`, `always_on_start` e `always_off`. Gate: `portal.tests.test_tenant_action_effect` prova Docker command + `tenant_policy` para aluno/admin; regressão completa 1015/1015; `VISUAL_DIFF=NO`. Evita ações visíveis que retornam 403 ou operam sobre parâmetros vazios por encadeamento de wrappers. Vale no Portal Python atual e deve ser preservado na migração C++23 como contrato de request forwarding e autorização por modo.

### L017 — portão de aprovação só existe se o caminho protegido for executado
Em 2026-08-27, a entrada 1520 executou o fluxo W/H/P pelo HTTP final do adaptador v2 com SQLite temporário. `homologation/enqueue` criou uma única fila idempotente e o negativo CSRF não produziu efeito; porém `production/enqueue` retornou 503 `NameError` antes de validar a aprovação porque `cloudif_portal_publications.py` chamava `hmac.compare_digest` sem importar `hmac`. O mesmo defeito fazia digest incorreto virar 503 em vez de 403. A correção adiciona o import ausente nas duas projeções versionadas byte-idênticas. Gate: `portal.tests.test_release_flow_action_effect` prova fila H, idempotência, CSRF negativo, vínculo aprovação/digest para P e digest inválido sem mutação; regressão completa 1021/1021; `VISUAL_DIFF=NO`. Evita tratar guard presente no código como guard efetivo sem executar a rota protegida. Vale no Portal Python atual; a migração C++23 deve preservar o binding entre candidato, aprovação, digest e fila, rejeitando divergência antes de qualquer mutação.

### L018 — “Checar projeto” deve consumir o status canônico dos três recursos
Em 2026-08-27, a entrada 1521 auditou o controle final **“Checar projeto”**, cuja superfície congelada declara verificar repositório, banco e vínculo do container sem alterar a configuração. O primeiro portão executável reprovou porque `check_project()` não retornava mapa observado e ignorava Supabase: lia apenas Forgejo/Komodo diretamente de `provision-report.json`. A correção reutiliza `cloudif_project_provision_status.status()` como fonte canônica para Forgejo, Supabase e Komodo, usa `PROVISION_ROOT` canônico e limita a mutação a estado observado (`repo_url`, `komodo_status`, `updated_at`), preservando nome, dono, descrição e tenant. Gate: `portal.tests.test_project_check_action_effect` prova os três recursos e a não mutação de configuração; regressão completa 1023/1023; `VISUAL_DIFF=NO`. Evita a interface afirmar “estado real” quando o backend avalia somente parte de um relatório possivelmente incompleto. Vale no Portal Python atual; a migração C++23 deve produzir o mesmo mapa de três recursos e o mesmo contrato de leitura sem reenfileirar nem reconfigurar.

### L019 — falha de sync imediato após commit não pode suprimir a reconciliação durável
Em 2026-08-27, a entrada 1522 executou **Gerenciar permissões** pelo handler final contra SQLite temporário, sync Komodo controlado e fila de reconciliação fake. Add/remove, bloqueio do dono e CSRF negativo já batiam com o contrato; o portão vermelho apareceu quando o sync Komodo falhou **depois** de `project_acl` ter sido commitada: `add_acl()`/`remove_acl()` levantavam exceção, o wrapper capturava o erro e não enfileirava `project.membership.changed`, deixando a fonte central alterada sem recuperação durável. A correção mantém a ACL central persistida, retorna estado de sincronização imediata pendente e permite ao wrapper sempre enfileirar a reconciliação durável. Gate: `portal.tests.test_project_acl_action_effect` prova DB, sync, fila, owner-block, CSRF negativo e falha sintética do Komodo; regressão completa 1027/1027; `VISUAL_DIFF=NO`. Evita estado parcialmente aplicado sem mecanismo de convergência. Vale no Portal Python atual e na migração C++23: após persistir a fonte central, falha de alvo externo deve produzir reconciliação/retry durável, nunca abortar o caminho que cria essa recuperação.

### L020 — validar parâmetros antes da primeira escrita do provisionamento
Em 2026-08-27, a entrada 1523 executou **Criar e provisionar projeto** pelo handler final com SQLite temporário, job durável controlado e fila de reconciliação fake. O portão positivo provou projeto, ACL do proprietário, job `queued` e `project.created`; o negativo de runtime não homologado reprovou porque `upsert_project()` fazia commit de `projects`/`project_acl` antes de validar runtime, PHP e keepalive. O usuário recebia erro 500, mas o projeto já existia parcialmente. A correção move essas validações para antes de abrir a transação de escrita. Gate: `portal.tests.test_project_create_action_effect` prova o caminho assíncrono 202 e efeito zero para runtime inválido/CSRF ausente; regressão completa 1030/1030; `VISUAL_DIFF=NO`. Evita objetos órfãos criados por requisições que deveriam ser rejeitadas. Vale no Portal Python atual e na migração C++23: toda validação determinística do pedido deve preceder a primeira mutação persistente; falha posterior exige mecanismo explícito de compensação/reconciliação.

### L021 — efeito externo concluído não pode voltar ao estado genérico `failed` por falha de finalização
Em 2026-08-28, a entrada 1526 executou a falha de `finalize` **depois** de `publish_homologated_candidate()` já ter ativado Produção. O portão vermelho mostrou dois modos incorretos: uma resposta 503 de finalize fazia `run_job()` marcar o job como `failed` mesmo quando a mesma reserva já aparecia `consumed` na releitura; e, quando a aprovação ainda estava `reserved`, o `except` chamava `release`, liberando uma autorização cujo efeito externo já havia sido aplicado. A correção relê `/v1/approvals?status=all` e aceita `consumed` somente quando o `reservation_id` é o mesmo; se ainda não consumida, marca job e `production_activation_requests` como `deployed_unfinalized`, mantém a reserva e não republica. Gate: `portal.tests.test_release_finalize_failure_effect` prova resposta perdida→sucesso e finalize pendente→estado parcial sem release/reclaim; regressão completa 1038/1038; `VISUAL_DIFF=NO`. Evita duplicar publish ou reaproveitar autorização depois de efeito crítico já aplicado. Vale no Portal Python atual e na migração C++23: após side effect confirmado, falha de finalize deve produzir estado parcial/reconciliável, nunca rollback lógico que reabra a autorização nem retry que repita o efeito.
### L022 — smoke de release chamado por `if` não pode depender de `set -e` implícito
Em 2026-08-28, a promoção real da correção **Visão geral** passou no shadow, copiou o candidato e reiniciou o Portal, mas o `apply` terminou `exit 1`: `smoke_live()` era chamado dentro de `if ! restart_service || ! smoke_live`, contexto em que Bash não aplica `set -e` como o autor esperava. Dois `curl` falharam durante a janela de restart, `smoke_url()` retornou cedo mantendo um `trap RETURN`, `smoke_live()` imprimiu `PORTAL_V2_LIB_LIVE_SMOKE=PASS` falso e o trap depois caiu em `root_page: unbound variable`. A correção remove cleanup por `RETURN`, acumula `rc` explicitamente e faz `smoke_live()` retornar falha antes de imprimir PASS. Gate: portão local executa `smoke_live` em contexto condicional com `curl` sinteticamente falho e exige rc não-zero, ausência de PASS falso e ausência de `unbound variable`; na Hospedagem, porta 19999 falhou limpo e o smoke real em 18094 passou. O live permaneceu no candidato `1ae42e1e...`, com `current` no candidato e `previous` no baseline `4407bd7c...`; verificador residente `errors=0`. Evita interpretar stdout otimista como saúde real e evita rollback/reaplicação indevida após promoção já saudável. Vale para scripts Bash de rollout do CloudIFF: qualquer função crítica chamada em condição deve propagar status explicitamente; `set -e` nunca é portão suficiente.
### L023 — runtime C++ só conta como substituto quando binário live, procedência e consumo funcional batem
Em 2026-08-28, a entrada 1527 auditou o caminho real **Portal → ingress NPM → NpmPublisherProvider C++**. Hospedagem `10.62.92.7` alcançou o ingress `10.62.91.3:80` com `Host: cloudif-publisher.internal`; health retornou 200 e token inválido 403. No host NPM, shadow v8 e live v10 retornaram 422 `ValueError/invalid_stage` com token válido e preservaram hashes de `state.json` e Nginx, provando efeito zero no negativo. Porém o binário live é `0.10.0-shadow` enquanto o branch auditado declara `0.36.0-shadow`, e o histórico Git disponível não estabelece qual commit produziu a release v10. Além disso `src/control/main.cpp` assina apenas `cloudiff.v2.node.observed`; não consome `project.created` nem `project.membership.changed`. Gate: `tests.test_npm_publisher_runtime_parity_evidence` cruza Portal, contrato, provider e evidência live; host NPM permaneceu sem deploy porque o verificador reportou `/` em 91%. Evita declarar “migrado para C++” por nome do serviço ou presença de código: a substituição exige paridade observada do caminho consumido, identidade/procedência do binário e cobertura real dos eventos/efeitos que substitui. Vale para toda migração C++23 do CloudIFF.
### L024 — gate da skill raiz não fixa versão histórica nem lê `current` como procedência
Em 2026-08-28, ao fechar a entrada 1528, `tests/test_cloudiff_project_skill.py` reprovou por dois pressupostos envelhecidos: exigia literalmente `cloudiff@0.1.5` e comparava os hashes históricos da reconciliação v40 contra `/srv/cloudif/agent-skills/current`. O primeiro tornava toda evolução homologada da skill uma falha; o segundo contradizia L011, pois `current` é ponteiro de execução mutável. A correção compara dinamicamente `skills/cloudiff/SKILL.md` com `competencias.yaml` e valida a evidência v40 pelos campos canônicos `repository`, `commit`, `path`, `versao_fixada` e `sha256`, mantendo paridade das versões fixadas atuais sem depender dos bytes instalados hoje. Gate: `tests/test_cloudiff_project_skill.py` passou com a versão atual e com os seis refs externos historicamente reconciliados. Evita gates autorreferentes que quebram a cada bump ou que reinterpretam runtime mutável como fonte histórica. Vale para toda validação estrutural de skill no CloudIFF.
### L025 — política de perfil C++ não equivale à migração dos efeitos W/H/P
Em 2026-08-28, a entrada 1529 auditou o `RuntimeExecutor` C++ contra os executores reais de HOMOLOGATION/CANARY/PRODUCTION na Forja. O planner C++ live `0.17.0-shadow` em `127.0.0.1:18232` planeja HOMOLOGATION e PRODUCTION com as políticas corretas e `side_effect_free=true`, mas `/v1/execute` retorna 409 `effects_not_enabled_v17`; o canary C++ `0.24.0-shadow` está inativo e, por contrato, só habilita efeitos para TEST/PREVIEW. Em paralelo, os serviços Python de homologação, canary e produção permanecem ativos nas portas 18217/18219/18220 e são os únicos que implementam estado durável current/previous, idempotência, smoke pré/pós switch, troca atômica de alias, rollback e, em produção, validação externa com restauração automática. O inventário Docker permaneceu byte-identificado por hash antes/depois do teste do planner. Gate: `tests.test_runtime_executor_whp_parity_evidence` cruza contrato, source, systemd, executores legados e evidência live. Evita declarar migração C++ pela presença das enums/policies: substituição W/H/P só é aceita quando o binário live com procedência conhecida executa os efeitos duráveis e de rollback equivalentes. Vale para toda migração de executor no CloudIFF.
### L026 — consumidor C++ de observação de nó não conta como reconciliação de eventos de projeto
Em 2026-08-28, a entrada 1531 auditou `project.created` e `project.membership.changed` ponta a ponta. Os produtores do Portal persistem cada pedido em SQLite `reconcile_requests`, fazem `fsync` de um marcador e `os.replace` atômico em `/var/lib/cloudif/reconcile-queue/incoming`; o worker Python particionado consome esses eventos, aplica membership/estado externo e grava status/retry/dead-letter. O `cloudiff-control` C++ live `0.15.0-shadow` está ativo, mas assina exclusivamente `cloudiff.v2.node.observed` e chama `PostgresClient::apply_observation`; os nomes dos eventos de projeto nem existem no source C++. A fila live estava sem itens não terminais; dois `project.membership.changed` antigos permanecem `dead_letter` com apenas `RuntimeError`, sem detalhe suficiente para replay seguro. Gate: `tests.test_project_events_cpp_reconciliation_evidence` cruza produtor, durabilidade, worker, control C++ e estado live. Evita confundir “há um control C++ ativo” com “a reconciliação de projeto foi migrada”: a substituição exige consumidor explícito dos mesmos eventos, partição/retry/deduplicação e efeitos equivalentes. Vale para qualquer migração de reconciliador/event consumer no CloudIFF.
### L027 — serviço C++ live e ingress dedicado não significam autoridade geral
Em 2026-08-28, a entrada 1533 auditou o `ArtifactEngine` C++ na Forja. O binário live `0.27.0-shadow` em `127.0.0.1:18226` passou autenticação e `/v1/toolchain/validate` real com efeito zero: hashes de imagens, containers e resultados persistentes ficaram idênticos. O ingress dedicado `cloudif-artifact-executor-v2.internal` restringe `POST /v1/build profile=classic-static-v2` e encaminha NPM → 18228 → 18226; o token clássico é escopado. Porém o host compartilhado `cloudif-artifact-executor.internal` continua apontando ao executor Python 18216, o worker durável ativo 0.15 aceita apenas noop/fail_once, e o `ClassicBuildWorker` 0.27 é oneshot manual/inativo, sem jobs clássicos ativos. Gate: `tests.test_artifact_executor_cpp_authority_evidence` cruza contratos, ingress, source, units e runtime. Evita declarar migração completa pela presença do C++ ou do ingress canary: autoridade só avança quando o consumidor contínuo real muda e os antigos caminhos podem ser retirados com prova. Vale para agentes/executores C++ do CloudIFF.
### L028 — release path, versão e BuildID não substituem commit-fonte
Em 2026-08-28, a entrada 1535 auditou a procedência dos binários live antigos NpmPublisher 0.10, RuntimeExecutor 0.17/0.24 e ArtifactEngine 0.27. Todos foram identificados por release path, SHA-256, GNU BuildID, timestamp e toolchain (`Ubuntu clang 21.1.8`), e alguns preservam scripts/journal de canary/rollout. Porém nenhuma release contém manifesto de source, nenhuma string/debug section preserva commit e o histórico C++ disponível nas 30 branches remotas começa em `2e869b7` de 24/08, depois das instalações de 20–21/08. A referência Git posterior ao artifact v27 é retrospectiva e não é build provenance. Gate: `tests.test_cpp_live_binary_provenance_evidence` exige `exact_source_commit=NAO DECLARADO` quando não há vínculo criptográfico. Para releases futuras, exigir `release-manifest.json` com `source_commit`, `source_tree`, `binary_sha256`, `gnu_build_id`, `compiler`, `build_command_digest` e `built_at`, ou build reproduzível independente com SHA idêntico ao live. Evita atribuir fonte por plausibilidade, versão ou proximidade temporal.
### L029 — planner C++ side-effect-free não substitui o gateway que decide e executa o upload
Em 2026-08-28, a entrada 1537 auditou o `mcp-upload` C++ live `0.20.0-shadow` em `127.0.0.1:18234`. O planner passou autenticação e um caso path-like realista com `side_effect_free=true`, sem filesystem, rede externa, mutação de workspace, persistência de URL ou vazamento do `/mnt/data`; sua resposta selecionou `workspace.artifact.upload.start`. Porém o MCP Gateway Python live não possui referência a `18234`/`MCP_UPLOAD`, continua expondo as cinco ferramentas de upload e executa os efeitos via Workspace Broker. A diferença entre o source base do gateway no branch e a release live não é drift: a linhagem é versionada por patches com hashes `948e... -> b218... -> f332...`, e o live bate o SHA final. O serviço C++ foi reiniciado em 28/08, mas reutilizou a release v20 cujo binário data de 21/08; reinício não é nova release nem satisfaz o gate de procedência. Gate: `tests.test_mcp_upload_cpp_authority_evidence` cruza contrato, source, unit, tools/list, planner live e linhagem do gateway. Evita declarar migração só porque um planner C++ responde corretamente; autoridade muda somente quando o consumidor live é explicitamente ligado ao novo componente e os efeitos equivalentes deixam de depender do caminho antigo.
### L030 — autoridade C++ pode ser aceita quando o consumidor live realmente atravessa o provider e o efeito fica separado
Em 2026-08-28, a entrada 1539 auditou o `SecureDistributionProvider` C++ live `0.22.0-shadow` no Maurício. Diferente dos planners shadow anteriores, este provider está no caminho real: NPM aceita somente GET de `10.62.92.7`, encaminha Authorization/audience/generation para `10.62.91.3:18240`, e o `cloudiff-v2-cert-sync` da Hospedagem usa exatamente esse origin/capability a cada 6h. O manifest autenticado retornou generation estável e dois membros; a auditoria baixou somente `fullchain.pem`, confirmou SHA header=corpo, generation idêntica e fingerprint igual ao certificado local, sem requisitar `privkey.pem`. Faro recebeu 403 no NPM e não possui capability. O provider guarda apenas SHA-256 do token; o token bruto fica root-only no consumidor. A instalação/validação do cert/key e HUP do NATS continuam efeito do `cert-sync`, não do provider. Gate: `tests.test_secure_distribution_cpp_authority_evidence` cruza contrato, source, hardening, NPM, capability, provider e consumidor live. Aceita autoridade C++ somente no escopo realmente consumido e preserva a fronteira entre distribuição read-only e mutação local. O binário 0.22 ainda não possui commit-fonte comprovado nem release manifest; restart de release antiga não satisfaz gate de procedência.
### L031 — dead-letter sem detalhe sanitizado impede diagnóstico causal posterior
Em 2026-08-28, T-016 reabriu somente em leitura os dois `project.membership.changed` históricos em `dead_letter`. As linhas persistidas guardavam apenas `RuntimeError`/`error_type`; os journals dos agentes já não cobriam as janelas de 05/08 e 07/08. O estado atual foi provado convergido em Portal/tenant/Forgejo/Komodo, e os terminais Komodo foram gravados segundos antes dos dead-letters, mas isso não permite declarar a causa exata histórica. Aprendizado: dead-letter de integração deve persistir detalhe sanitizado por etapa/upstream (status, etapa e erro não secreto) suficiente para reconstrução posterior; `error_type` isolado não é observabilidade causal. T-016 também mostrou que falha de onboarding deve ser tratada separadamente porque o booleano de membership usa apenas Forgejo, Komodo e tenant-access. Evita replay especulativo quando o estado atual já convergiu.
### L032 — autoridade observacional exige consumidor real e prova de não mutação
Em 2026-08-28, T-021 completou o gate live do `AdminObservability` C++ `0.34.0-shadow` em `127.0.0.1:18260`. Health e endpoint ativos não foram suficientes: a prova atravessou o consumidor real do Portal (`/cloudiff/portal/api/admin-observability` e `/api/node-recovery-policy`), confirmou 403 para não-admin e 200 para `CloudIF-Tenants-Admin`, e comparou PostgreSQL antes/depois dos GETs. `desired_state` (`count=2`, soma de revisions `4`) e `audit_log` de `node_recovery_policy_changed` (`count=0`) permaneceram idênticos; nenhum POST de recovery foi executado. Assim, a autoridade C++ é aceita no escopo **read-only observacional**, sem alegar paridade do efeito de recovery. O binário live não possui `release-manifest.json`, a versão 0.34 não aparece no histórico remoto C++ e o commit-fonte exato permanece `NAO DECLARADO`. Gate: `tests.test_admin_observability_cpp_live_evidence`. Evita promover serviço por presença de endpoint ou misturar leitura provada com efeito de controle não exercido.
### L033 — replay efeito deve preservar dead-letter e expor falha por etapa antes de nova tentativa
Em 2026-08-28, T-016R executou, com autorização humana explícita, replay dos dois `project.membership.changed` históricos. O mecanismo correto criou novos requests e preservou os dead-letters originais. A primeira geração falhou 5/5 porque o Forja Agent encerrava a conexão com `NameError: safe_slug is not defined`; o worker agregador persistia apenas `RuntimeError`, ocultando o upstream. A correção mínima reutilizou `_v118_slug`, helper já existente, em uma release derivada do próprio live para evitar carregar drift do branch. Após health 200, validação direta mostrou Forgejo/Komodo/tenant-access `ok=true`; uma segunda geração dos dois eventos concluiu `ready` em 1/1, sem colaboradores adicionados/removidos e sem terminais novos. Onboarding continuou `returncode=1` e permanece T-031 separado porque não participa do booleano membership. Regra: replay autorizado preserva histórico, corrige o menor defeito comprovado, valida a etapa upstream e só então cria nova geração; nunca reabre rows históricos em lugar.
### L034 — `ReadWritePaths` inexistente falha em `226/NAMESPACE` antes do processo e pode aparecer no consumidor como `URLError`
Em 2026-08-28, T-031 reconstruiu a falha repetida do `project-onboarding-reconcile`: Forja e Komodo respondiam 200 no último ciclo falho, mas o `cloudif-supabase-release-agent.service` reiniciava em loop com `status=226/NAMESPACE` porque `/srv/cloudif/managed-backups/releases`, declarado em `ReadWritePaths`, não existia. O Python do Release Agent nem chegava a iniciar; o onboarding via apenas `URLError`. Trabalho concorrente criou o diretório `0700 root:root` e reiniciou o serviço às 01:04:37 UTC; `/supabase/release/inspect` retornou 200 às 01:04:49/51 e o onboarding passou 2/2 às 01:04:51, permanecendo saudável nos ciclos seguintes. Regra: bootstrap/deploy de unit sandboxed deve materializar e validar todos os alvos de `ReadWritePaths`/`ReadOnlyPaths` antes de start/restart e provar health antes que consumidores dependam do upstream. Diagnóstico deve distinguir falha de namespace systemd de falha da aplicação. Gate: `tests.test_project_onboarding_urllerror_evidence`.
### L035 — gate de segurança live não pode confundir semântica de acesso com classes CSS/labels frágeis
Em 2026-08-28, T-036 diagnosticou `cloudif-ui-security-review.service` em `failed`: o report live tinha HTTP 200 para professor/admin e todos os headers de segurança esperados verdes, mas 5 checks de UI falhavam porque `cloudif-ui-security-tests.py` ainda exigia `nav/app/page/profile-card/profile-role` e `Administração do AD`, enquanto o Portal live congelado usa `enterprise-nav/ui143-nav`, `profile-chip`, `portal-hero` e o rótulo `Administração`. O gate live e a cópia versionada eram byte-idênticos, e `portal/tests/test_ui_security_gate_contract.py` institucionalizava os mesmos marcadores antigos, inclusive proibindo `portal-hero`/`profile-chip teacher`. Assim, a suíte estática podia permanecer verde enquanto o gate periódico live falhava. Regra: gates de segurança devem afirmar invariantes semânticas (HTTP, papel/visibilidade, skip-link/aria, headers/policies) e apenas pinarem marcadores visuais versionados quando isso for requisito explícito; o teste de contrato do gate deve evoluir junto com a interface congelada. Gate: `tests.test_ui_security_review_stale_gate_evidence`.
### L036 — dead-letter diagnóstico deve ser estruturado, sanitizado e não confiar em `str(exc)` genérico
Em 2026-08-29, T-033 corrigiu a lacuna que obrigou T-016/T-016R a reconstruir um `RuntimeError` sem causa: o reconcile worker passou a persistir `stage`, `upstream`, `status`, `code` e `detail` sanitizado em colunas `last_error_*` e no `diagnostic` do dead-letter, preservando `error_type` e `secrets_exposed=false`. O teste com SQLite real provou retry, dead-letter, migração incremental e limpeza do contexto no sucesso. Bearer, assignments sensíveis e userinfo de URL são redigidos; exceção genérica persiste somente o tipo e nunca `str(exc)`, porque mensagens de biblioteca podem carregar credencial sem rótulo. A política de 5 tentativas, lease e backoff não mudou. Regra: observabilidade de falha persistente deve usar contexto causal explicitamente curado; mensagem arbitrária de exceção não é dado seguro para armazenamento. Gate: `tests.test_reconcile_deadletter_observability` + compatibilidade T-016/T-016R.
### L037 — timeout de homologação deve atravessar o contrato até o build real
Em 2026-09-03, a homologação H3 de um repositório grande continuou falhando após aumentar apenas o timeout HTTP do Portal: o Portal enviava `timeout=900`, mas o Komodo Agent consumia exclusivamente `build_timeout` e mantinha silenciosamente o `docker build` em 300 s. O sintoma observável era `Remote end closed connection without response`, seguido de `context canceled` no build, sem restart/OOM do agente. A correção homologada envia explicitamente `build_timeout` e mantém no agente compatibilidade com `timeout`; o H3 seguinte concluiu em 9m20s, container saudável, HTTPS 200/TLS válido e candidato imutável gerado. Gate: entrada 987/U05, testes de contrato 21/21, `py_compile`, `diff --check`, secret scan, job H3 `succeeded` e artefato `sha256:e811d342288db5ba3e00583dc5eb15ee48fb223e967839a4602f11900792fcd0`. Evita aumentar timeout na camada errada e confundir fechamento de conexão com falha do Docker/Komodo. Vale para Portal + Komodo Agent quando materialização local da imagem usa `docker build` síncrono.
### L038 — estado SQLite do Komodo precisa ser concorrente por construção
Em 2026-09-04, o portão U07 criou projetos em sessões independentes e, enquanto `teste-5` era provisionado, excluiu `teste-3`. A exclusão falhou em `runtime_destroy` com `sqlite3.OperationalError: database is locked`, apesar de os projetos serem distintos. O Komodo Agent executava inicialização/schema SQLite em requisições multithread sem WAL, `busy_timeout` e lock de schema. A correção homologada centraliza conexões com `busy_timeout=30000`, ativa WAL, protege schema com `RLock` e torna a inicialização process-local idempotente. Gate: entrada 849/988/U07, teste com 16 threads e 240 leituras/escritas sem lock, retry real de exclusão durante criação concluído, zero novos `database is locked` após deploy e exclusão simultânea de `teste-4`/`teste-5` concluída em jobs distintos. Evita que operação de um projeto bloqueie ou derrube outra operação independente. Vale em Linux/Python multithread/SQLite no Komodo Agent.

### L039 — recuperação de criação interrompida precisa voltar à última etapa segura
Na mesma U07, a primeira corrida deixou `teste-5` com Forgejo, Komodo e Supabase prontos, mas sem `template-applied.json`/`managed-runtime.json`; o retry comum chegava a `initial-publication` e ficava irrecuperável porque a etapa de template nunca havia sido materializada. A correção homologada recupera `runtime_template`, `php_version`, `runtime_layout` e `template_kind` do job de criação anterior quando os marcadores duráveis não existem e define `resume_from=template`; o worker reaplica somente o template faltante e continua a publicação sem recriar projeto, repositório ou banco. Gate: entradas 658/659/U07, testes de recuperação 18/18 e recuperação real de `teste-5` até `status=succeeded`, publicação 1017 e HTTPS 200. Evita transformar falha concorrente parcial em projeto sem caminho de convergência. Vale no fluxo Portal→worker de provisionamento com jobs persistidos e etapas idempotentes.
### L040 — aprovação crítica expirada precisa ser renovável sem consumir o próximo P
Em 2026-09-04, o gate final do `teste-sofa` revelou que `production/approval/request` devolvia indefinidamente a autorização P2 expirada porque a linha local ainda estava `pending`. O efeito observável era HTTP 200 com `existing=true`, `status=expired`, deixando a interface sem caminho para obter nova dupla aprovação. A correção homologada consulta o status real do serviço de aprovação: `pending`, `pending_second`, `approved` e `reserved` permanecem idempotentes; `expired`, `rejected` e `cancelled` encerram a autorização anterior e criam outra vinculada ao mesmo `candidateNumber` e ao mesmo `publicationNumber`, recalculando o digest do ambiente atual. Gate: U08, primeira chamada após deploy retornou `renewed=true`, novo `approvalId`, `status=pending`, `publicationNumber=2`; repetição imediata retornou `existing=true` para o novo ID; `production/enqueue` continuou recusado com 403 enquanto a dupla aprovação humana não existir. Evita transformar expiração de TTL em bloqueio permanente e evita pular P2 para P3 apenas por renovar autorização. Vale no Portal W/H/P com Approval Service transacional e numeração P reservada somente por release publicada.
### L041 — gate humano crítico precisa ser descobrível na navegação principal
Em 2026-09-04, durante a U10/U11, a aprovação P2 existia no Approval Service e a página `?tab=aprovacoes` renderizava a solicitação, mas o usuário não conseguiu encontrá-la pela navegação normal: o shell v2 mantinha `Aprovações` apenas na navegação contextual de projeto e em atalhos secundários. O portão de navegação reprovou porque a barra principal de uma sessão owner listava Visão geral, Publicações, Projetos, Bancos e tenants, Backup, Conectores e Ajuda, sem `Aprovações`. A correção homologada inclui `Aprovações` diretamente em `Painel geral` e mantém também o contexto de projeto; RBAC não muda. Gate: entrada 1352/U11, 30/30 testes de shell/arquitetura, deploy `u11-approvals-nav-d824ff6-20260904`, página Projetos HTTP 200 com link primário único para `?tab=aprovacoes`, página Aprovações HTTP 200 com `aria-current=page`, solicitação P2 pendente visível e owner ainda `can_decide=false`. Evita que uma operação tecnicamente correta fique bloqueada porque o usuário não consegue descobrir onde tomar a decisão humana. Vale no Portal v2 server-side shell com Approval Service separado e navegação contextual de projeto.
### L042 — identidade humana de aprovação precisa ser normalizada antes de comparar solicitante e aprovador
Em 2026-09-04, a U13 mostrou que uma ativação P2 solicitada como `portal:iff1742962` aceitou a primeira decisão enviada como `iff1742962`, embora o contrato de ativação crítica proíba o próprio solicitante de aprovar. O Approval Service comparava strings cruas e tratava o prefixo de namespace `portal:` como identidade diferente. A correção homologada normaliza somente o namespace humano `portal:` para comparações de `requester`/`approver` e de primeiro/segundo aprovador, preservando o valor armazenado para auditoria. Gate: entrada 1516/U13, 31/31 testes; teste vivo sintético criou aprovação crítica, comprovou 409 `requester_cannot_approve_activation` para `portal:qa-human` versus `qa-human`, aceitou um primeiro aprovador distinto e comprovou 409 `distinct_second_approver_required` para a mesma pessoa com/sem prefixo; a pendência sintética foi cancelada ao final. Evita que variação de namespace burle separação de funções em dupla aprovação. Vale no Approval Service com solicitantes humanos namespaced como `portal:<username>`.

### L043 — UI de dupla aprovação deve refletir o ator e o estágio, não só o papel global
Na mesma U13, após a primeira aprovação real, a interface ainda oferecia novamente `Aceitar/Aprovar` ao primeiro aprovador e a segunda tentativa terminava numa página genérica `Acesso negado`, embora o backend estivesse em `pending_second`. A correção homologada passa o username ao renderer, oculta ações impossíveis para o solicitante e para o primeiro aprovador, mostra mensagens explícitas de espera e não oferece `Rejeitar` em `pending_second` porque o contrato atual do Approval Service não aceita essa operação. Conflitos de formulário obsoleto recebem mensagem específica. Gate: entrada 1516/U13, 30/30 testes de UI e reteste real da P2 renovada: `portal:iff1742962` vê “Você solicitou esta ativação”, sem botões de decisão, tanto em Aprovações quanto no card do Teste Sofá em Conectores; API independente confirma `pending` e zero aprovadores. Evita botão que promete uma decisão que o backend obrigatoriamente recusará. Vale no Portal server-side com renderers `cloudif_approval_panel` e `cloudif_ai_agents_guide`.
### L044 — CSS contextual fora da camada legacy deve usar tokens definidos no escopo global
Em 2026-09-04, a U15 reproduziu no Chromium real que o item contextual **Aprovações** ficava praticamente branco/transparente no tema escuro: `.project-context-group a[aria-current="page"]` usava `--accent`/`--accent-soft`, tokens definidos somente dentro de `.legacy-content`, enquanto a navegação contextual vive fora desse escopo. A correção homologada foi deliberadamente limitada a `.tab-aprovacoes`, usando `--iff-dark` e `--iff-wash`, já definidos em `tokens.css` para claro/escuro. Gate: entrada 1517/U15, 27/27 testes e navegação viva Projetos→Aprovações em tema dark; o item ativo passou a `rgb(149, 223, 163)` sobre `rgb(23, 53, 31)`, sem erro de console, pageerror ou request falhada. Evita declaração CSS inválida que cai silenciosamente para cor herdada e perde o estado ativo em temas alternativos. Vale no shell v2 quando elementos ficam fora do bridge `.legacy-content`.

### L045 — histórico volumoso de aprovação deve ser carregado sob demanda na própria página
Na mesma U15, o browser mostrou 18 aprovações históricas expandidas antes da seção **Sempre permitir**, empurrando as políticas persistentes vários milhares de pixels para baixo. A correção mantém somente estados operacionais (`pending`, `pending_second`, `approved`) no fluxo principal e move estados terminais para um `<dialog>` nativo aberto pelo botão **Carregar histórico (N)**; nenhuma API ou regra de aprovação foi alterada. Gate: entrada 1517/U15, navegador real em tema escuro confirmou botão único, **Sempre permitir** visível a cerca de 821 px, modal abrindo com 18 registros e fechando novamente, zero erros JS/rede. Evita que auditoria histórica atrapalhe a decisão atual e as políticas persistentes. Vale no painel server-side `cloudif_approval_panel` com histórico crescente.
### L046 — módulo legacy claro precisa de bridge dark explícita quando injeta cores hard-coded
Em 2026-09-04, a U16 reproduziu no Chromium móvel que a aba **Código** preservava o shell escuro, mas os quadros internos do assistente e dos projetos continuavam brancos. O módulo `cloudif_git_komodo_module.py` injeta `#fff`/tons claros em `.ci-section`, `.ci-step`, `.ci-project-card`, menus e formulários; somente trocar o fundo do shell não corrige esses descendentes. A correção homologada foi limitada a `.tab-git .legacy-content` e remapeou as superfícies visíveis para `--surface`, `--surface-2`, `--rule`, `--ink`, `--ink-3`, `--iff-wash` e `--iff-dark`. Gate: entrada 1518/U16, 24/24 testes e navegação real Reconciliação→Código em Chromium 390 px; `whiteCount=0`, fundo do body `rgb(7, 17, 11)`, item Código verde sobre verde escuro e `scrollWidth==clientWidth`. Evita páginas híbridas em que o shell respeita dark mode mas widgets legacy permanecem claros. Vale enquanto o módulo Git/Komodo ainda emite CSS hard-coded.

### L047 — negativa HTTP de uma rota visual deve preservar o status e ainda usar o shell canônico
Na mesma U16, **Produção** devolvia corretamente HTTP 403 para o usuário, porém o coexist adapter só transformava HTML com status 200; o 403 escapava como página legacy desformatada. A correção permite adaptar especificamente o 403 de `operacao-producao` e devolve o mesmo status original após a transformação. Gate: navegação viva em Chromium dark confirmou título `Produção · CloudIFF`, navegação contextual presente, Produção ativa, mensagem `Projeto não autorizado.`, fundo/cores canônicos e nenhuma exposição da página legacy crua; verificação independente continuou retornando HTTP 403. Evita que segurança correta produza uma experiência visual fora do contrato sem enfraquecer autorização. Vale para negativas HTML intencionais que precisam permanecer fail-closed.
### L048 — bridge de tema deve usar tokens realmente definidos e ser validada por estilo computado
Em 2026-09-04, a U17 encontrou os últimos elementos claros da aba **Código** no Chromium móvel: identificadores `<code>` e badges (`Vinculado`, `Configurado`, `Online`) ainda resolviam para fundos claros do CSS legacy. A primeira correção eliminou o branco, mas usou `--surface-2`, token inexistente no design system; o navegador descartou a declaração e produziu fundo transparente. A correção homologada usa somente tokens existentes: identificadores e estados positivos em `--iff-wash`/`--iff-dark`, estados neutros em `--surface`/`--ink-2`. Gate: entrada 1519/U17, 19/19 testes e navegação viva em Chromium dark; `teste-sofa`, tenant, `Vinculado`, `Configurado` e `Online` computaram fundo `rgb(23, 53, 31)`, texto `rgb(149, 223, 163)`, nenhum chip alvo ficou com luminância clara (`lightCount=0`) e não houve overflow horizontal. Evita fixes de tema aparentemente corretos no código mas invalidados silenciosamente pelo CSS por variável ausente. Vale para qualquer bridge entre CSS legacy e tokens do shell v2.
### L049 — relay externo 443-only deve separar superfície pública de destinos internos
Em 2026-09-05, a U19 homologou acesso remoto sem nova porta WAN: `sslh` mantém o listener público único em TCP/443, TLS/HTTPS segue para o Nginx Proxy Manager em `127.0.0.1:10443` e SSH segue para um gateway dedicado em `127.0.0.1:10022`. O Portal Authentik/ACL emite lease curta por projeto e chave Ed25519 temporária entregue uma vez; o gateway usa `permitopen=` e cache local fail-closed para restringir cada sessão aos destinos autorizados. A Hospedagem, que não é roteável diretamente a partir do proxy, mantém um conector SSH de saída pela própria 443 e cria `RemoteForward` apenas enquanto existe lease ativa; o relay de PostgreSQL fica em loopback e some após release/expiração. Gate vivo: HTTPS e SSH compartilharam a 443, Forgejo respondeu `SSH-2.0-Go`, PostgreSQL respondeu ao SSLRequest pelo túnel, destino não declarado foi bloqueado, e release derrubou sessão estabelecida em 21s e removeu o listener reverso. Não confundir “lease temporária” com “porta WAN temporária”: 443 permanece pública; a autorização e os forwards internos é que surgem/somem.

### L050 — auditoria de exposição WAN precisa verificar filtros, não apenas NAT
Na U19, a porta pública 22 apareceu em varredura externa apesar de não existir NAT WAN para 22. A causa foi uma regra legada de filtro `Allow all ipv4+ipv6 via pfSsh.php`, que aceitava qualquer protocolo para a WAN/self. A regra foi removida com backup prévio; o aceite externo passou a mostrar somente 80 e 443 abertas e 22/2222/5432/54404/6543/10022/10443/18360-18362/24000-24999 fechadas ou filtradas. Regra operacional: política “somente web pública” exige inventário conjunto de NAT, regras de filtro e listeners do próprio firewall, seguido de sonda independente externa. SSH administrativo permanece apenas em redes internas/VPN.

### L051 — scope transitório Docker inativo pode bloquear wake de tenant até ser descarregado
Durante a homologação PostgreSQL da U19, o banco do tenant `iff1742962-testesofa` falhou ao iniciar porque o scope transitório `docker-<container-id>.scope` estava `inactive (dead)` porém ainda `loaded`; o runtime recusava recriá-lo com “already loaded or has a fragment file”. O reparo seguro foi restrito ao scope daquele container: `systemctl stop`, `systemctl reset-failed`, `systemctl daemon-reload`, confirmar `LoadState=not-found` e então repetir `docker start`. O banco voltou `healthy`; ao fim do teste todo o tenant foi devolvido ao estado parado. Não reiniciar Docker inteiro quando a divergência está isolada a um scope transitório de um container.
