# CloudIFF / PGH — identidades, cofre OpenBao e permissões

Atualização: 17/11/2026 UTC. Aplicação: infra-01, dev-01, dev-02,
aud-01, surface-01 e doc-01.

Regra principal: localizar, autenticar e validar a identidade de integração
EXISTENTE antes de solicitar outra ou criar usuário novo.

## Contas históricas — funções diferentes

| Identidade | Função registrada | Evidência atual e precaução |
| --- | --- | --- |
| cloudif-bot | Git Provider Account do Komodo para Forgejo cloudiff.duckdns.org/git; histórico de configuração KOMODO_GIT_ACCOUNT e KOMODO_GIT_PROVIDER em junho/2026. | Não confundir com Git Provider homônimo do GitHub. Existência e permissão atuais somente via API Komodo autenticada. |
| cloudif-agent | Usuário técnico de automação do Komodo; registro anterior com admin=true, super_admin=false e escopos de build/servidor. | Registro é histórico, não concessão atual. Testar status, ACL e validade da credencial sem ler seu valor. |
| cloudif-integrator | Conta específica de integração com Tuleap. | Não pressupor identidade Komodo/OpenBao. |
| svc-pgh-cloudiff | Nova service user proposta no PR45 para integração mínima. | Manifesto PENDING_ADMIN_CREATION e verified_in_komodo=false. Não criar duplicata sem reconciliação. |

Komodo Core observado em 10.62.91.2:9120, HTTP200 na interface, mas
sem sessão administrativa autenticada nesta execução. HTTP200 não prova
conta existente, função administrativa nem disponibilidade de API key.

## Como funciona o cofre (COF / OpenBao)

1. Identificar quem executa: AREA/cloudiff/CODIGO no PGH, principal real,
   machine_ref, service_ref, capability, ambiente e duração solicitada.
2. PGH Credential Broker vincula a identidade AUTENTICADA de execução
   ao CredentialBinding permitido, conferindo agente/máquina/serviço,
   projeto, secret_ref, capacidade e TTL. Não confiar só no texto do agente.
3. Broker usa o OpenBao como provedor de segredo; fornece ao consumidor
   um identificador opaco, handle/lease curto, escopo e expiração.
   Nunca registrar o valor em prompt, chat, Git, HTML, Atlas ou memória PGH.
4. Consumidor executa apenas operação autorizada; confirmar própria
   capacidade permitida, negações em outro projeto/serviço, TTL,
   renovação/revogação e registro de auditoria sem plaintext.
5. Ao encerrar, expirar/revogar o lease; não salvar credencial em origin
   Git, log, arquivo de build, captura de interface ou texto de agente.

Estado real IFF2 em 17/11: OpenBao homologação 2.6.2 saudável,
initialized=true, sealed=false; broker legado pgh-vault-agent autentica
transporte SSH restrito, mas NÃO houve confirmação de KV produtivo, escrita
de segredo ou permissão administrativa. Serviço produtivo da IFF2 não
identificado e readiness G2 continua BLOCKED/UNVERIFIED. Não usar
homologação como produção.

## Quando faltar permissão — procedimento obrigatório

1. Retomar PGH e consultar este guia, ACCESS.md da identidade e Atlas.
2. Reconciliar cloudif-agent (conta técnica Komodo), cloudif-bot
   (Git Provider Forgejo), cloudif-integrator (Tuleap) e outras contas.
   Consultar API AUTENTICADA atual, não arquivo histórico ou tela pública.
3. Verificar status/role/grants reais e a operação mínima de leitura;
   quando pertinente testar acesso negado a recurso alheio.
4. Se a identidade existente for suficiente, solicitar capacidade e
   TTL mínimos pelo broker corporativo com secret_ref/handle efêmero.
5. Se faltar acesso, registrar owner, change-ID, lock, projeto,
   machine_ref, service_ref, principal, capacidade, ambiente, TTL,
   justificativa e evidência não sensível; atribuir a infra-01.
   Aud-01 revisa segregação, menor privilégio e trilha de auditoria.
6. Criar service user NOVA apenas quando não houver principal adequado
   e um administrador Komodo efetivamente autenticado autorizar.
   Não escrever SQL diretamente no banco Komodo nem reutilizar
   credenciais de Git como identidade administrativa.
7. Confirmar por readback autenticado, testes allowed/denied,
   TTL/revocation, auditoria e eventual rollback; registrar apenas IDs
   não secretos e timestamps no PGH/Atlas.
8. Em caso de impossibilidade real, registrar BLOCKED_AUTHENTICATION,
   BLOCKED_PERMISSION ou BLOCKED_PRODUCTION_VAULT. Não inventar token,
   elevar privilégios, contornar SSH/ACL ou declarar concluído.
   Credencial informada no chat não é sessão de API conectada.

G0–G5 continuam obrigatórios para modificações produtivas:
identidade/lock, restore institucional, OpenBao produtivo,
Docker/lease/rollback, rotação Git e auditoria independente.

## Responsabilidades

- infra-01: verificar identidades e grants reais, owner, delegação Komodo,
  cofre produtivo, backup, TLS, ACL/TTL e renovação/revogação.
- dev-01: implementar consumidores de secret_ref e falha fechada,
  sem persistência de credenciais nos jobs/containers.
- dev-02: manter inventário Git Provider correto, Atlas, CI e vínculos,
  com proveniência, sem dados sensíveis.
- aud-01: validar fronteira de confiança do broker, negações, TTL,
  trilha de auditoria, segregação de projetos, G0–G5 e P0 Git.
- surface-01: testes de interface apenas com autenticação autorizada;
  conferir que valores secretos não aparecem em UI/logs.
- doc-01: atualizar runbook, instruções compartilhadas, PGH/Atlas e
  distinguir histórico de estado operacional comprovado.

## Evidências e referências, sem segredos

- evidencias/AUDITORIA-AUD01-OPENBAO-PATCH-BROKER-2026-11-14.md
- evidencias/OPENBAO-G2-IFF2-OWNER-ACTIVATION-20261116.md
- evidencias/DOC01-KOMODO-OPENBAO-AUTH-STATUS-20261117.md
- service-accounts/komodo/svc-pgh-cloudiff.json (proposta)
- Atlas: cloudiff.tool.openbao (catálogo, NÃO cofre)
- PR45 CloudIFF (plano de service user, não criação)

P0 ainda aberto: 22 arquivos Git config com URL autenticada, sem
rotação/revogação comprovada; quantidade de arquivos não é quantidade
de tokens distintos. Não salvar valores em documentação.
