---
name: cloudiff
versao: 0.1.12
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
  versao_fixada: '14'
  delta_lido_ate: 2a641bfe597377a55711ea0804c602ea999fda07
  estado: reconciliado
- id: github-incremental-reconciliation
  fonte: debianlima/competencias-catalogo:metodo/github-incremental-reconciliation/SKILL.md
  versao_fixada: '7'
  delta_lido_ate: 2a641bfe597377a55711ea0804c602ea999fda07
  estado: reconciliado
- id: governanca-ontologica-de-skills
  fonte: debianlima/competencias-catalogo:metodo/governanca-ontologica-de-skills/SKILL.md
  versao_fixada: 1.0.4
  delta_lido_ate: 2a641bfe597377a55711ea0804c602ea999fda07
  estado: reconciliado
- id: telemetry-data-visualization
  fonte: debianlima/competencias-catalogo:dominio/telemetry-data-visualization/SKILL.md
  versao_fixada: '2'
  delta_lido_ate: 2a641bfe597377a55711ea0804c602ea999fda07
  estado: reconciliado
- id: distributed-agent-control
  fonte: debianlima/competencias-catalogo:dominio/distributed-agent-control/SKILL.md
  versao_fixada: '1'
  delta_lido_ate: 2a641bfe597377a55711ea0804c602ea999fda07
  estado: reconciliado
- id: network-ssh-operations
  fonte: debianlima/competencias-catalogo:dominio/network-ssh-operations/SKILL.md
  versao_fixada: '1'
  delta_lido_ate: 2a641bfe597377a55711ea0804c602ea999fda07
  estado: reconciliado
- id: operational-ui-truth
  fonte: debianlima/competencias-catalogo:dominio/operational-ui-truth/SKILL.md
  versao_fixada: '1'
  delta_lido_ate: 2a641bfe597377a55711ea0804c602ea999fda07
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

1. carregar `desenvolvedor-de-software@14`;
2. verificar `trabalho_compartilhado`/zona de exclusão;
3. reconciliar com `github-incremental-reconciliation@7`;
4. emitir `DELTA_INVENTORY=PASS` e `LEARNING_PRESERVED=PASS`;
5. aplicar `governanca-ontologica-de-skills@1.0.4` quando tocar skill/catálogo/relação;
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
