# Auditoria global CloudIFF — adequação Preview → Homologação → Produção

Data: 22/11/2026. Esta versão substitui a visão anterior limitada a 8 projetos e preserva as remediações históricas em documentos próprios.

## Escopo

- **25 IDs públicos** em `project_public_ids`.
- Read-model `release_flow_status()` para W/H/P e histórico.
- Integrações Forgejo/Komodo/Supabase quando cadastradas.
- Navegação com Chrome/Selenium real no WebDev da Forja.
- Probes de URL W/P/alias e confirmação de runtimes pelo Executor nos projetos operacionais.
- Nenhuma promoção H→P foi disparada por esta auditoria.

## Contrato obrigatório

- `docs/PADRAO-CLOUDIFF-PREVIEW-HOMOLOGACAO-PRODUCAO-20261120.md`
- `docs/RUNBOOK-PADRAO-CLOUDIFF-WHP-CONTINUIDADE.md`
- `docs/FLUXO-WHP-PUBLICACAO.md`
- `docs/AGENDA-P1020-PROCEDIMENTO-GERENCIAMENTO-PUBLICACOES.md`

## Readiness/browser

- Browser: `cloudiff-webdev-browser` na **Forja** (`cloudiff-webdev.service`).
- Readiness corrigido para exigir Selenium `ready=true` e conectividade HTTPS interna ao Portal CloudIFF.
- Navegação de auditoria usa resolução interna `*.cloudiff.duckdns.org → 10.62.91.3` somente na sessão Chrome, evitando hairpin pelo IP público.
- Rodada de validação: **49/49 superfícies navegadas pelo Chrome**; o resultado funcional de cada superfície permanece registrado por projeto.
- Faro é o nó mais leve observado nesta rodada e passa a ser **preferência para novos serviços auxiliares**, condicionado a gates de rede, backup, capacidade e compatibilidade. Serviços existentes não são migrados automaticamente.

## Matriz atual

| Nº | Projeto | Integração | Preview | Produção | Browser/destaque | Classificação |
|---:|---|---|---|---|---|---|
| 1001 | `laboratorio-de-hardware` | `ready` | `W1` / True | `P12` | alias: Login - Lab Hardware; preview: Login - Lab Hardware; production: Login - Lab Har… | **PARCIAL_PRODUCAO_LEGADA** |
| 1002 | `silvipro` | `ready` | `W1` / True | `P1` | alias: silvipro · primeiros passos; preview: silvipro · primeiros passos; production: s… | **PARCIAL_PRODUCAO_LEGADA_PLACEHOLDER** |
| 1003 | `silvipro2` | `não cadastrada` | `—` / None | `—` | Authentik/Portal | **LEGADO_NAO_PROVISIONADO** |
| 1004 | `lima-teste` | `não cadastrada` | `—` / None | `—` | Authentik/Portal | **LEGADO_TESTE_NAO_PROVISIONADO** |
| 1005 | `teste-lima` | `não cadastrada` | `—` / None | `—` | Authentik/Portal | **LEGADO_TESTE_NAO_PROVISIONADO** |
| 1006 | `lima-teste-3` | `não cadastrada` | `—` / None | `—` | Authentik/Portal | **LEGADO_TESTE_NAO_PROVISIONADO** |
| 1007 | `silvipro-jt-2026` | `não cadastrada` | `W1` / False | `—` | preview: silvipro-jt-2026 · primeiros passos | **PREVIEW_LEGADO_PLACEHOLDER** |
| 1008 | `teste` | `não cadastrada` | `—` / None | `—` | Authentik/Portal | **LEGADO_TESTE_NAO_PROVISIONADO** |
| 1010 | `teste-sofa` | `não cadastrada` | `W1` / False | `—` | preview: teste-sofa · primeiros passos | **PREVIEW_LEGADO_PLACEHOLDER** |
| 1011 | `tuleap-laboratorio-de-hardware` | `não cadastrada` | `—` / None | `—` | Authentik/Portal | **LEGADO_NAO_PROVISIONADO** |
| 1014 | `grupix` | `não cadastrada` | `W1` / False | `—` | preview: 502 | **QUEBRADO_PREVIEW_502** |
| 1015 | `teste-4` | `não cadastrada` | `—` / None | `—` | Authentik/Portal | **LEGADO_TESTE_NAO_PROVISIONADO** |
| 1016 | `teste-3` | `não cadastrada` | `—` / None | `—` | Authentik/Portal | **LEGADO_TESTE_NAO_PROVISIONADO** |
| 1017 | `teste-5` | `não cadastrada` | `—` / None | `—` | Authentik/Portal | **LEGADO_TESTE_NAO_PROVISIONADO** |
| 1018 | `testando123` | `não cadastrada` | `W1` / False | `—` | preview: 502 | **QUEBRADO_PREVIEW_502** |
| 1019 | `hardness-e2e-0254` | `não cadastrada` | `W1` / False | `—` | preview: hardness-e2e-0254 · primeiros passos | **ATIVO_TESTE_HARDNESS** |
| 1020 | `agenda-unica` | `ready` | `W3` / True | `P11` | alias: Agenda Única; preview: Agenda Única; production: Agenda Única | **CONFORME_REFERENCIA** |
| 1021 | `cpuhub` | `ready` | `W1` / True | `P5` | alias: Acesso · CPUHub; preview: Acesso · CPUHub; production: Acesso · CPUHub | **PARCIAL_PRODUCAO_LEGADA** |
| 1022 | `cadales` | `ready` | `W1` / True | `P2` | alias: cadales · primeiros passos; preview: cadales · primeiros passos; production: cad… | **PARCIAL_PRODUCAO_LEGADA_PLACEHOLDER** |
| 1023 | `isha` | `não cadastrada` | `W1` / False | `—` | preview: isha · primeiros passos | **PREVIEW_LEGADO_PLACEHOLDER** |
| 1024 | `mvplanner` | `não cadastrada` | `W1` / False | `—` | preview: mvplanner · primeiros passos | **PREVIEW_LEGADO_PLACEHOLDER** |
| 1025 | `paperclip` | `ready` | `W1` / True | `—` | preview: Paperclip | **BLOQUEADO_RUNTIME_COMPOSTO_STABLE_502** |
| 1026 | `sgrep-v2` | `adopted_existing_staging` | `W1` / True | `—` | preview: SGREP - Fine Comp | **PREVIEW_SOURCE_LINKED_SEM_PRODUCAO** |
| 1027 | `msha` | `degraded` | `—` / None | `—` | Authentik/Portal | **DEGRADADO_INTEGRACAO** |
| 1028 | `pghd-contexto` | `não cadastrada` | `—` / None | `—` | Authentik/Portal | **REGISTRO_INFRA_NAO_PROVISIONADO** |

## Prioridade de remediação

### P0/P1 — falha operacional ou integração

- **Paperclip 1025:** Preview real saudável, mas stable 502 e D1 legado fora do modelo moderno; manifest/volume e rota precisam ser reconciliados com gate do proprietário.
- **MSHA 1027:** integração degradada (`tenant_runtime_error`) e sem Preview.
- **Grupix 1014 / Testando123 1018:** W1 confirmado 502 pelo Chrome.

### P1/P2 — migração ao contrato moderno

- Laboratório de Hardware, CPUHub, Cadales e SilviPro têm runtime W/P acessível, mas a Produção atual é legado histórico; o próximo release humano deve ser H→mesma H em P.
- Cadales e SilviPro ainda servem página `primeiros passos`; isso é gap de conteúdo/fonte, não falha de proxy.
- SGREP v2 tem Preview source-linked saudável, mas ainda precisa contrato explícito para H/P.

### Legado/teste sem pipeline moderno

- IDs sem integração/Preview devem permanecer sem novos recursos até finalidade e proprietário serem confirmados.
- Previews legados que apenas servem `primeiros passos` não devem ser promovidos automaticamente.
- `hardness-e2e-0254` permanece ferramenta de teste/hardness, não Produção por padrão.

## Próximas ondas

1. Corrigir P0/P1 com lease por projeto, prestate e rollback.
2. Migrar projetos operacionais legados no próximo ciclo humano H→P, sem reconstrução entre H e P.
3. Reconciliar projetos com Preview órfão/placeholder somente depois de confirmar ownership e Forgejo canônico.
4. Manter Agenda Única como regressão obrigatória do padrão.
5. A tarefa **T-044** registra a futura aba Banco para PostgreSQL/MySQL embutido por estágio; não implementar durante esta sincronização.

## Auditorias individuais

- 1001 `laboratorio-de-hardware`: `docs/audits/publication-standard/20261122/laboratorio-de-hardware.md`
- 1002 `silvipro`: `docs/audits/publication-standard/20261122/silvipro.md`
- 1003 `silvipro2`: `docs/audits/publication-standard/20261122/silvipro2.md`
- 1004 `lima-teste`: `docs/audits/publication-standard/20261122/lima-teste.md`
- 1005 `teste-lima`: `docs/audits/publication-standard/20261122/teste-lima.md`
- 1006 `lima-teste-3`: `docs/audits/publication-standard/20261122/lima-teste-3.md`
- 1007 `silvipro-jt-2026`: `docs/audits/publication-standard/20261122/silvipro-jt-2026.md`
- 1008 `teste`: `docs/audits/publication-standard/20261122/teste.md`
- 1010 `teste-sofa`: `docs/audits/publication-standard/20261122/teste-sofa.md`
- 1011 `tuleap-laboratorio-de-hardware`: `docs/audits/publication-standard/20261122/tuleap-laboratorio-de-hardware.md`
- 1014 `grupix`: `docs/audits/publication-standard/20261122/grupix.md`
- 1015 `teste-4`: `docs/audits/publication-standard/20261122/teste-4.md`
- 1016 `teste-3`: `docs/audits/publication-standard/20261122/teste-3.md`
- 1017 `teste-5`: `docs/audits/publication-standard/20261122/teste-5.md`
- 1018 `testando123`: `docs/audits/publication-standard/20261122/testando123.md`
- 1019 `hardness-e2e-0254`: `docs/audits/publication-standard/20261122/hardness-e2e-0254.md`
- 1020 `agenda-unica`: `docs/audits/publication-standard/20261122/agenda-unica.md`
- 1021 `cpuhub`: `docs/audits/publication-standard/20261122/cpuhub.md`
- 1022 `cadales`: `docs/audits/publication-standard/20261122/cadales.md`
- 1023 `isha`: `docs/audits/publication-standard/20261122/isha.md`
- 1024 `mvplanner`: `docs/audits/publication-standard/20261122/mvplanner.md`
- 1025 `paperclip`: `docs/audits/publication-standard/20261122/paperclip.md`
- 1026 `sgrep-v2`: `docs/audits/publication-standard/20261122/sgrep-v2.md`
- 1027 `msha`: `docs/audits/publication-standard/20261122/msha.md`
- 1028 `pghd-contexto`: `docs/audits/publication-standard/20261122/pghd-contexto.md`
## Remediações globais executadas na própria auditoria

- Readiness WebDev da Forja corrigido: health agora exige Selenium `ready=true` **e** conectividade HTTPS do container até o NPM interno.
- Harness canônico `scripts/audit-cloudiff-browser-readiness.py` registra navegação Chrome sem armazenar credenciais; 49/49 superfícies da rodada foram navegadas.
- Publisher: removidas todas as rotas H sem candidata/runtime e W2/W3 que não correspondiam ao Preview fixo atual; certificados preservados. Após a limpeza não existe bridge H ativa.
- Executor: órfão do Laboratório (`dep_2d71...`) e dois H órfãos do Grupix foram marcados `inactive`; volumes/snapshots preservados.
- Estado Compose final: somente Agenda P11 e Laboratório P12 permanecem `running`; não existe deployment Compose de Homologação rodando.
- Paperclip D1 não foi desligado porque existe conflito de autoridade entre labels de canário PGH e estado legado `active_deploy=1`; exige decisão do proprietário.
