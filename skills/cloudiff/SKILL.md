---
name: cloudiff
versao: 0.1.11
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
  delta_lido_ate: 9b951d0d2f68a3ead190741fd5e8b4d6cc8e0a84
  estado: reconciliado
- id: github-incremental-reconciliation
  fonte: debianlima/competencias-catalogo:metodo/github-incremental-reconciliation/SKILL.md
  versao_fixada: '7'
  delta_lido_ate: 9b951d0d2f68a3ead190741fd5e8b4d6cc8e0a84
  estado: reconciliado
- id: governanca-ontologica-de-skills
  fonte: debianlima/competencias-catalogo:metodo/governanca-ontologica-de-skills/SKILL.md
  versao_fixada: 1.0.5
  delta_lido_ate: 9b951d0d2f68a3ead190741fd5e8b4d6cc8e0a84
  estado: reconciliado
- id: telemetry-data-visualization
  fonte: debianlima/competencias-catalogo:dominio/telemetry-data-visualization/SKILL.md
  versao_fixada: '2'
  delta_lido_ate: 9b951d0d2f68a3ead190741fd5e8b4d6cc8e0a84
  estado: reconciliado
- id: distributed-agent-control
  fonte: debianlima/competencias-catalogo:dominio/distributed-agent-control/SKILL.md
  versao_fixada: '1'
  delta_lido_ate: 9b951d0d2f68a3ead190741fd5e8b4d6cc8e0a84
  estado: reconciliado
- id: network-ssh-operations
  fonte: debianlima/competencias-catalogo:dominio/network-ssh-operations/SKILL.md
  versao_fixada: '1'
  delta_lido_ate: 9b951d0d2f68a3ead190741fd5e8b4d6cc8e0a84
  estado: reconciliado
- id: operational-ui-truth
  fonte: debianlima/competencias-catalogo:dominio/operational-ui-truth/SKILL.md
  versao_fixada: '1'
  delta_lido_ate: 9b951d0d2f68a3ead190741fd5e8b4d6cc8e0a84
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
### L015 — timeout de homologação deve atravessar o contrato até o build real
Em 2026-09-03, a homologação H3 de um repositório grande continuou falhando após aumentar apenas o timeout HTTP do Portal: o Portal enviava `timeout=900`, mas o Komodo Agent consumia exclusivamente `build_timeout` e mantinha silenciosamente o `docker build` em 300 s. O sintoma observável era `Remote end closed connection without response`, seguido de `context canceled` no build, sem restart/OOM do agente. A correção homologada envia explicitamente `build_timeout` e mantém no agente compatibilidade com `timeout`; o H3 seguinte concluiu em 9m20s, container saudável, HTTPS 200/TLS válido e candidato imutável gerado. Gate: entrada 987/U05, testes de contrato 21/21, `py_compile`, `diff --check`, secret scan, job H3 `succeeded` e artefato `sha256:e811d342288db5ba3e00583dc5eb15ee48fb223e967839a4602f11900792fcd0`. Evita aumentar timeout na camada errada e confundir fechamento de conexão com falha do Docker/Komodo. Vale para Portal + Komodo Agent quando materialização local da imagem usa `docker build` síncrono.
### L016 — estado SQLite do Komodo precisa ser concorrente por construção
Em 2026-09-04, o portão U07 criou projetos em sessões independentes e, enquanto `teste-5` era provisionado, excluiu `teste-3`. A exclusão falhou em `runtime_destroy` com `sqlite3.OperationalError: database is locked`, apesar de os projetos serem distintos. O Komodo Agent executava inicialização/schema SQLite em requisições multithread sem WAL, `busy_timeout` e lock de schema. A correção homologada centraliza conexões com `busy_timeout=30000`, ativa WAL, protege schema com `RLock` e torna a inicialização process-local idempotente. Gate: entrada 849/988/U07, teste com 16 threads e 240 leituras/escritas sem lock, retry real de exclusão durante criação concluído, zero novos `database is locked` após deploy e exclusão simultânea de `teste-4`/`teste-5` concluída em jobs distintos. Evita que operação de um projeto bloqueie ou derrube outra operação independente. Vale em Linux/Python multithread/SQLite no Komodo Agent.

### L017 — recuperação de criação interrompida precisa voltar à última etapa segura
Na mesma U07, a primeira corrida deixou `teste-5` com Forgejo, Komodo e Supabase prontos, mas sem `template-applied.json`/`managed-runtime.json`; o retry comum chegava a `initial-publication` e ficava irrecuperável porque a etapa de template nunca havia sido materializada. A correção homologada recupera `runtime_template`, `php_version`, `runtime_layout` e `template_kind` do job de criação anterior quando os marcadores duráveis não existem e define `resume_from=template`; o worker reaplica somente o template faltante e continua a publicação sem recriar projeto, repositório ou banco. Gate: entradas 658/659/U07, testes de recuperação 18/18 e recuperação real de `teste-5` até `status=succeeded`, publicação 1017 e HTTPS 200. Evita transformar falha concorrente parcial em projeto sem caminho de convergência. Vale no fluxo Portal→worker de provisionamento com jobs persistidos e etapas idempotentes.
### L018 — aprovação crítica expirada precisa ser renovável sem consumir o próximo P
Em 2026-09-04, o gate final do `teste-sofa` revelou que `production/approval/request` devolvia indefinidamente a autorização P2 expirada porque a linha local ainda estava `pending`. O efeito observável era HTTP 200 com `existing=true`, `status=expired`, deixando a interface sem caminho para obter nova dupla aprovação. A correção homologada consulta o status real do serviço de aprovação: `pending`, `pending_second`, `approved` e `reserved` permanecem idempotentes; `expired`, `rejected` e `cancelled` encerram a autorização anterior e criam outra vinculada ao mesmo `candidateNumber` e ao mesmo `publicationNumber`, recalculando o digest do ambiente atual. Gate: U08, primeira chamada após deploy retornou `renewed=true`, novo `approvalId`, `status=pending`, `publicationNumber=2`; repetição imediata retornou `existing=true` para o novo ID; `production/enqueue` continuou recusado com 403 enquanto a dupla aprovação humana não existir. Evita transformar expiração de TTL em bloqueio permanente e evita pular P2 para P3 apenas por renovar autorização. Vale no Portal W/H/P com Approval Service transacional e numeração P reservada somente por release publicada.
### L019 — gate humano crítico precisa ser descobrível na navegação principal
Em 2026-09-04, durante a U10/U11, a aprovação P2 existia no Approval Service e a página `?tab=aprovacoes` renderizava a solicitação, mas o usuário não conseguiu encontrá-la pela navegação normal: o shell v2 mantinha `Aprovações` apenas na navegação contextual de projeto e em atalhos secundários. O portão de navegação reprovou porque a barra principal de uma sessão owner listava Visão geral, Publicações, Projetos, Bancos e tenants, Backup, Conectores e Ajuda, sem `Aprovações`. A correção homologada inclui `Aprovações` diretamente em `Painel geral` e mantém também o contexto de projeto; RBAC não muda. Gate: entrada 1352/U11, 30/30 testes de shell/arquitetura, deploy `u11-approvals-nav-d824ff6-20260904`, página Projetos HTTP 200 com link primário único para `?tab=aprovacoes`, página Aprovações HTTP 200 com `aria-current=page`, solicitação P2 pendente visível e owner ainda `can_decide=false`. Evita que uma operação tecnicamente correta fique bloqueada porque o usuário não consegue descobrir onde tomar a decisão humana. Vale no Portal v2 server-side shell com Approval Service separado e navegação contextual de projeto.
### L020 — identidade humana de aprovação precisa ser normalizada antes de comparar solicitante e aprovador
Em 2026-09-04, a U13 mostrou que uma ativação P2 solicitada como `portal:iff1742962` aceitou a primeira decisão enviada como `iff1742962`, embora o contrato de ativação crítica proíba o próprio solicitante de aprovar. O Approval Service comparava strings cruas e tratava o prefixo de namespace `portal:` como identidade diferente. A correção homologada normaliza somente o namespace humano `portal:` para comparações de `requester`/`approver` e de primeiro/segundo aprovador, preservando o valor armazenado para auditoria. Gate: entrada 1516/U13, 31/31 testes; teste vivo sintético criou aprovação crítica, comprovou 409 `requester_cannot_approve_activation` para `portal:qa-human` versus `qa-human`, aceitou um primeiro aprovador distinto e comprovou 409 `distinct_second_approver_required` para a mesma pessoa com/sem prefixo; a pendência sintética foi cancelada ao final. Evita que variação de namespace burle separação de funções em dupla aprovação. Vale no Approval Service com solicitantes humanos namespaced como `portal:<username>`.

### L021 — UI de dupla aprovação deve refletir o ator e o estágio, não só o papel global
Na mesma U13, após a primeira aprovação real, a interface ainda oferecia novamente `Aceitar/Aprovar` ao primeiro aprovador e a segunda tentativa terminava numa página genérica `Acesso negado`, embora o backend estivesse em `pending_second`. A correção homologada passa o username ao renderer, oculta ações impossíveis para o solicitante e para o primeiro aprovador, mostra mensagens explícitas de espera e não oferece `Rejeitar` em `pending_second` porque o contrato atual do Approval Service não aceita essa operação. Conflitos de formulário obsoleto recebem mensagem específica. Gate: entrada 1516/U13, 30/30 testes de UI e reteste real da P2 renovada: `portal:iff1742962` vê “Você solicitou esta ativação”, sem botões de decisão, tanto em Aprovações quanto no card do Teste Sofá em Conectores; API independente confirma `pending` e zero aprovadores. Evita botão que promete uma decisão que o backend obrigatoriamente recusará. Vale no Portal server-side com renderers `cloudif_approval_panel` e `cloudif_ai_agents_guide`.
### L022 — CSS contextual fora da camada legacy deve usar tokens definidos no escopo global
Em 2026-09-04, a U15 reproduziu no Chromium real que o item contextual **Aprovações** ficava praticamente branco/transparente no tema escuro: `.project-context-group a[aria-current="page"]` usava `--accent`/`--accent-soft`, tokens definidos somente dentro de `.legacy-content`, enquanto a navegação contextual vive fora desse escopo. A correção homologada foi deliberadamente limitada a `.tab-aprovacoes`, usando `--iff-dark` e `--iff-wash`, já definidos em `tokens.css` para claro/escuro. Gate: entrada 1517/U15, 27/27 testes e navegação viva Projetos→Aprovações em tema dark; o item ativo passou a `rgb(149, 223, 163)` sobre `rgb(23, 53, 31)`, sem erro de console, pageerror ou request falhada. Evita declaração CSS inválida que cai silenciosamente para cor herdada e perde o estado ativo em temas alternativos. Vale no shell v2 quando elementos ficam fora do bridge `.legacy-content`.

### L023 — histórico volumoso de aprovação deve ser carregado sob demanda na própria página
Na mesma U15, o browser mostrou 18 aprovações históricas expandidas antes da seção **Sempre permitir**, empurrando as políticas persistentes vários milhares de pixels para baixo. A correção mantém somente estados operacionais (`pending`, `pending_second`, `approved`) no fluxo principal e move estados terminais para um `<dialog>` nativo aberto pelo botão **Carregar histórico (N)**; nenhuma API ou regra de aprovação foi alterada. Gate: entrada 1517/U15, navegador real em tema escuro confirmou botão único, **Sempre permitir** visível a cerca de 821 px, modal abrindo com 18 registros e fechando novamente, zero erros JS/rede. Evita que auditoria histórica atrapalhe a decisão atual e as políticas persistentes. Vale no painel server-side `cloudif_approval_panel` com histórico crescente.
