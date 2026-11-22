# Runbook técnico — padrão CloudIFF Preview → Homologação → Produção

## Finalidade

Este documento é o ponto de retomada técnica para agentes que precisem operar ou evoluir o fluxo de publicação CloudIFF sem depender do contexto de uma conversa anterior. Ele descreve **contrato, implementação, fontes de verdade, portões, testes, rollback e evidência**.

O padrão vale globalmente para projetos gerenciados pelo Portal. Particularidades de um projeto entram como evidência operacional, nunca alteram as invariantes abaixo.

## 1. Invariantes do fluxo

1. O projeto possui **um Preview fixo Wn**. O número `n` preserva a identidade histórica já existente; projeto existente não é renumerado para W1. Projeto novo pode começar em W1.
2. Mudança no Forgejo atualiza **o mesmo Preview**. Não criar um novo Preview a cada commit.
3. Enviar para Homologação congela/clona integralmente o estado aprovado do Preview. H não acompanha mudanças posteriores do Forgejo.
4. Promover H para P reutiliza **a mesma instância homologada**, sem rebuild entre H e P.
5. Após nova P ativa, as P anteriores ficam **Offline** por padrão e só consomem runtime se o humano escolher `Subir`.
6. `Subir Pn` publica somente a URL versionada Pn. Não altera o endereço principal.
7. `Ativar no endereço principal` é a única ação que troca o alias público principal. A versão alvo precisa ficar saudável antes do cutover; a anterior só é desativada depois.
8. `Desligar` remove bridge/rota versionada e deixa o runtime histórico inativo, preservando recursos de rollback conforme o tipo de runtime.
9. `Excluir container` nunca é permitido para a P ativa. Em P histórica Compose-snapshot, remove o runtime e preserva o snapshot. Em P histórica legada inativa, a exclusão pode ser final (`legacy-final`) após validação estrita de identidade/labels/alias; nesse caso não há reidratação automática.
10. Estado visual `Online/Offline/Containers excluídos` vem do runtime real, não apenas do banco do Portal.

## 2. Endereço principal versus endereço versionado

- URL versionada: `<numero>-pN-publication.cloudiff.duckdns.org` — usada para teste/histórico.
- URL numérica estável: `<numero>.cloudiff.duckdns.org` — compatibilidade operacional.
- Alias principal do projeto: `<alias>.cloudiff.duckdns.org` — endereço exibido ao humano e alvo de `Ativar no endereço principal` quando cadastrado em `project_publication_aliases`.

`release_flow_status()` devolve `primaryHostname` e `primaryUrl`. A UI nunca deve inferir o alias a partir do slug.

## 3. Variáveis e secrets por estágio

- Preview, Homologação e Produção têm configurações independentes depois da clonagem/promoção.
- W→H herda as variáveis existentes no Preview; H→P herda as da Homologação.
- Alterações posteriores atingem somente o estágio selecionado.
- Humano autenticado no Portal usa `human/save`: sessão + CSRF + ACL já são autorização. Não criar Approval Service para esse salvamento.
- MCP/automação mantém plan/approval/execute conforme o contrato próprio.
- Secrets aparecem mascarados. Campo vazio mantém; novo valor rotaciona/aplica; plaintext não retorna ao navegador/log/evidência.
- `POSTGRES_PASSWORD` tem migração interna com `DATABASE_URL`, health e rollback. `POSTGRES_DB`/`POSTGRES_USER` são mudanças estruturais.
- Digest de variáveis usa JSON canônico UTF-8 (`ensure_ascii=false`) em Portal/Komodo/Executor.

### UX de salvamento

Depois que controller **e runtime** confirmam a revisão, o modal `Variáveis de ambiente` fecha automaticamente, emite `cloudif:environment-config-applied` e recarrega o ambiente que está por baixo. Não deixar a tela presa em `Salvando e aplicando…` após sucesso.

Implementação principal: `components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py`, função JavaScript `envSave()`.

## 4. PHP / Node.js / Terminal são stage-aware

Diagnóstico sempre recebe `environment=preview|homologation|production` e resolve containers daquele estágio.

- Preview Compose vinculado: serviços reais da stack fixa, por exemplo `api` + `web`.
- Homologação/Produção Compose: containers do `deployment_id` da H/P correspondente.
- Se PHP/Node não está instalado, isso **não é falha da plataforma**. Retornar `ok=true`, `available=false`, listar os runtimes efetivamente presentes e identificar o estágio/container.
- Terminal usa a mesma identidade de estágio; não escolher stack-base/legado por conveniência.

Implementação:
- Portal: `runtime_diagnostic_target()` em `cloudif_portal_publications.py`.
- UI/API: `publicationRuntimeLoad()` e `_rd_runtime_info_with_reconcile()` em `cloudif-admin-portal-base.py`.
- Komodo: `cloudif_project_runtime_info()`.

## 4.1 Preview composto: gate antes de Homologação

O snapshot genérico de Preview só é válido quando o container registrado representa a aplicação completa. Se o Wn usa app + gateway/sidecar, banco/volume próprio ou outros serviços, **não** congelar apenas o gateway com `docker commit`.

O Komodo deve recusar o snapshot genérico com `preview_composite_runtime_requires_manifest` quando detectar um app irmão `cloudif-p<numero>-w<geracao>-preview-app` ou um `org.cloudiff.artifact-kind` de sidecar/gateway. A operação deve falhar antes de commit Git, imagem H ou candidato no Portal.

Nessa situação é obrigatório definir um manifest/runtime completo com política explícita para serviços e dados. O gate é de segurança: nunca contornar criando H parcial só para avançar o fluxo.

## 5. Histórico de Produção

### Offline → Subir

`historical_publication_prepare()`:
1. confirma ACL/owner e que Pn não é a ativa;
2. para runtime preservado, usa `multiservice-reactivate phase=prepare`;
3. para runtime explicitamente excluído e baseado em Compose snapshot, reidrata o snapshot;
4. cria bridge versionada Pn;
5. registra somente o stage Pn no Publisher;
6. valida URL versionada;
7. **não** muda o alias principal.

### Online → Desligar

`historical_publication_stop()` remove stage/bridge e devolve runtime a `inactive`, preservando a capacidade de reativação.

### Offline/Online → Ativar no endereço principal

`rollback_publication()` é o cutover histórico e deve manter o rollback robusto:
- preparar/alcançar saúde da P alvo;
- criar/validar URL versionada;
- ativar bridge;
- publicar alias principal;
- validar o alias principal externamente;
- confirmar runtime alvo;
- só então desativar deployment/bridge/stage da Produção anterior;
- em erro após o switch, tentar restaurar runtime/bridge/Publisher da Produção anterior e abortar o alvo.

Nunca substituir essa função por uma versão simplificada que perca o bloco `restore-current-*`.

### Excluir container

`historical_publication_delete_runtime()`:
- somente owner/admin;
- somente P inativa;
- `compose-snapshot`: remove bridge/stage/deployment runtime e preserva o snapshot;
- `legacy-final`: Komodo valida container esperado, labels do projeto/estágio/número e ausência do alias ativo antes de remover o container;
- em ambos os modos, a publicação passa a `archived` e sai do histórico operacional;
- snapshot/auditoria técnica permanecem internos quando existirem;
- legado sem snapshot retorna `canRehydrate=false` e não volta a oferecer `Subir`/`Ativar` após a exclusão.

A reidratação só existe para modos que possuem artefato/snapshot reconstruível. Nunca apresentar um legado sem imagem/snapshot como reidratável.

## 6. Reidratação histórica Compose

A nova Produção normal **continua proibida** de ser criada diretamente de snapshot. Esse gate não deve ser removido.

Quando o humano apagou explicitamente o runtime de uma P histórica, o Executor oferece a operação interna `/v1/compose-snapshots/rehydrate-historical`:

1. valida `project_slug`, `snapshot_id`, `snapshot_digest` e digest histórico;
2. restaura o snapshot como Homologação técnica;
3. chama `promote_compose_deployment()` para promover **a mesma instância** para `production`;
4. não cria bridge nem altera rota estável;
5. retorna `rehydratedThroughHomologation=true`, `sameHomologatedDeployment=true`, `stableRouteChanged=false`.

O Portal deriva um novo `deployment_id` determinístico a partir da exclusão histórica e persiste esse ID no `detail_json` da P.

O Executor live possui uma linhagem mais nova que a árvore canônica atual. Até a reconciliação global dessa linhagem, a implementação exata desta operação está versionada em `compat/cloudiff-historical-production-rehydrate-executor.patch`. **Não substituir o Executor live pelo arquivo canônico antigo.**

## 7. Preview Wn

`_fixed_preview_generation(slug)` preserva o maior `preview_generation` histórico válido do projeto. Bridges/URL/terminal/snapshot devem usar o mesmo Wn.

Migração de identidade deve ser sem downtime:
1. criar nova bridge Wn apontando para o mesmo runtime;
2. publicar rota Wn;
3. validar health externo;
4. somente então remover rota/bridge incorreta anterior.

Nunca recriar DB/stack do Preview só para corrigir o número Wn.

## 8. Limpeza de resíduos

- H promovida não deve permanecer como runtime H residual.
- P históricas podem existir como metadata/snapshot, mas ficam Offline por padrão.
- Containers legados fora do Publisher atual devem ser inventariados por host, labels, portas, systemd/Nginx/Publisher antes de parar.
- Parar é preferível a remover quando ainda não há prova de rollback.
- Remoção de runtime histórico somente pelo fluxo `Excluir container`. Para Compose, exigir snapshot reidratável; para legado, permitir `legacy-final` apenas em P inativa e após validação de identidade/labels/alias pelo Komodo.

## 9. Fontes de verdade e reconciliação

- Portal DB: identidade W/H/P, alias, histórico e ACL.
- Project Config Controller: catálogo/auditoria de variáveis.
- Executor: estado real de deployments/snapshots/containers Compose.
- Komodo Agent: gateway/terminal/diagnóstico e Preview.
- Publisher: rotas versionadas e alias estável.
- Docker/host: verdade descritiva de container/rede/volume.

Se live e Git divergem, fazer reconciliação incremental. Nunca copiar um arquivo canônico antigo por cima do live sem comparar funções/hashes. Patches `compat/live-extra-*.patch` registram deltas já detectados.

## 10. Testes mínimos antes de aceitar uma mudança

1. `python3 -m py_compile` em todo Python alterado.
2. `git diff --check`.
3. suíte Portal de publicação/variáveis/overview.
4. health Preview Wn.
5. health Produção versionada ativa.
6. health alias principal.
7. P histórica: `Subir` não muda alias; `Desligar` volta 202/offline.
8. se testar `Excluir`: snapshot `ready` antes; excluir; confirmar alias intacto; reidratar; validar mesmo snapshot/digest; desligar de novo.
9. PHP/Node: confirmar estágio/container real e comportamento `available=false` quando tecnologia ausente.
10. scan de secrets nos arquivos/patches/evidências.

## 11. Próxima unidade obrigatória: auditoria global dos projetos

Após estabilizar o projeto de referência, auditar **todos os projetos cadastrados** contra este padrão. Para cada projeto registrar:

- Preview fixo Wn e URL/bridge coerentes;
- origem Forgejo e atualização in-place;
- H congelada e promoção da mesma instância;
- ausência de H residual após promoção;
- P ativa única e alias principal correto;
- P históricas Offline por padrão;
- Subir/Desligar/Ativar/Excluir conforme capacidade do runtime;
- variáveis/secrets por estágio e salvamento humano direto;
- diagnóstico PHP/Node/Terminal stage-aware;
- resíduos de containers em todos os hosts;
- health HTTP e revisão do runtime;
- drift live × Git e patches de compatibilidade;
- evidência e rollback.

Nenhum projeto deve ser marcado `conforme` apenas porque responde HTTP 200; a auditoria precisa provar identidade, rota, estado e capacidade de rollback.

## 12. Recuperação do Preview fixo não incrementa Wn

Uma falha/recriação do container interno **não cria um novo Wn**. `ensure` deve restaurar o mesmo slot público. No runtime contínuo v144, o container interno pode ter nome estável (`cloudif-p<numero>-preview-web`), mas precisa manter o alias Docker `cloudif-p<numero>-w1-preview-web` (ou a identidade pública Wn equivalente) esperado pelo gateway.

Incrementar geração é uma operação deliberada de mudança de identidade e não deve acontecer como efeito colateral de health/recovery. Teste obrigatório: executar `ensure` duas vezes e comprovar mesmo Wn, mesmo stack e mesmo container ID.

## 13. Backup de metadata em remediações: mínimo e sem lock prolongado

Para correções de **poucas linhas de metadata** em bancos SQLite operacionais, não copiar integralmente o banco live durante tráfego. O banco do Komodo Agent pode ter vários GB; uma operação `sqlite3.backup()` longa pode manter conexões/threads presos e fazer requisições retornarem `database is locked` após o `busy_timeout`.

Preferir, nesta ordem:

1. fluxo oficial de backup da plataforma, quando a finalidade é backup completo;
2. snapshot direcionado das linhas que serão alteradas + `docker inspect`/artefatos necessários ao rollback;
3. transação CAS (`BEGIN IMMEDIATE`, precondições de identidade, alteração mínima, commit) para a mutação.

Um backup direcionado deve registrar valores anteriores suficientes para um `restore.sql`/JSON reproduzível e não incluir secrets. Se uma cópia integral ad hoc for interrompida, ela não é evidência confiável: substituí-la por rollback mínimo validado e remover o arquivo parcial criado pela própria unidade.

Se um backup longo deixar o processo do agente com transação/conexão presa, primeiro encerrar **somente o processo inequivocamente pertencente à unidade**, provar que nenhum outro backup concorrente foi tocado e, se necessário, reiniciar apenas o serviço do agente para liberar conexões SQLite. Depois executar um `BEGIN IMMEDIATE` de prova antes de continuar.

### Preview source-linked

Projetos com Preview provisionado por infraestrutura externa podem registrar `project_preview_source_links`. Esse vínculo é uma fonte válida de read-model quando não existe Preview multiservice/genérico gerenciado. O Portal deve validar `stage_code`, URL pública e status antes de retornar `runtimeKind=source-linked-preview`; nunca recriar o stack só para fazer o painel reconhecê-lo.

O status Git desse contrato é `linked`, não `synced`, salvo quando houver um sincronizador explícito. Diagnóstico de runtime deve usar os containers de aplicação registrados no source-link, não apenas o gateway. Terminal source-linked exige contrato próprio com validação de ACL + labels do container; não apontar silenciosamente para outra Stack.

## Read-model do Portal e histórico operacional

As superfícies humanas não devem varrer filesystem nem consultar todos os runtimes a cada clique. Use `portal_readmodel_cache` como índice descartável em SQLite, pré-aquecido pelo `cloudif-portal-refresh-cache.timer` e invalidado pelas mutações. O índice acelera a leitura, mas nunca substitui a fonte de verdade; em ausência/expiração ele é reconstruído.

Ações humanas que mudam Projeto, Conector, Aprovação ou Publicação devem invalidar a chave correspondente e disparar refresh assíncrono. Projetos/Publicações podem continuar lendo diretamente tabelas canônicas do Portal para dados baratos; somente enriquecimentos remotos/filesystem entram no read-model.

`Excluir container` de P histórica significa também retirar essa P do **histórico operacional**: após remover o runtime de forma segura, marcar os registros de publicação como `archived`. Snapshot e auditoria técnica permanecem internos quando existirem, e a P não continua aparecendo com botões na interface. P Compose usa exclusão reidratável por snapshot; P legada inativa pode usar exclusão final validada pelo Komodo e então não terá reidratação automática.
