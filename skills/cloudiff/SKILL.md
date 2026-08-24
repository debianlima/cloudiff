---
name: cloudiff
versao: 0.1.0
description: Governa, reconcilia, normaliza e evolui o CloudIFF V1→V2 C/C++ preservando integralmente a interface homologada, contratos, compatibilidade e capacidade de rollback.
tipo_competencia: projeto
---

# Skill de projeto CloudIFF

## Invariante mestre

`FrozenPortalInterface` é o requisito máximo do projeto. Visão geral, Publicações, Projetos e Bancos/tenants, além de seus fluxos visíveis homologados, não podem mudar por consequência da migração tecnológica. Migrar Python para C/C++ muda implementação, nunca a experiência visual já homologada. Qualquer mudança visual exige autorização humana explícita separada.

## Método obrigatório

Toda unidade segue, nesta ordem:

1. `desenvolvedor-de-software@14` para selecionar entrada elegível, dependências e portões;
2. `github-incremental-reconciliation@7` para inventariar deltas e preservar aprendizados;
3. emitir `DELTA_INVENTORY=PASS` e `LEARNING_PRESERVED=PASS` antes de normalizar;
4. `governanca-ontologica-de-skills@1.0.4` quando a unidade tocar skills, relações ou catálogo;
5. normalizar apenas o estado já reconciliado;
6. executar portões mecânicos independentes;
7. quando a unidade exigir o node Faro, implementar e provar no Faro real `10.62.91.5` durante a própria conciliação;
8. atualizar aprendizado desta skill somente depois de homologação comprovada.

## Referências correlatas

- `distributed-agent-control@1`: agentes, heartbeat, comando, update, fencing e idempotência.
- `telemetry-data-visualization@2`: telemetria e apresentação administrativa baseada em fonte observada.
- `network-ssh-operations@1`: SSH, roteamento, VPN e conectividade por camadas.
- `operational-ui-truth@1`: UI operacional deve refletir fonte viva e passar Playwright/snapshot.
- competências CloudIFF já instaladas e declaradas em `competencias.yaml`: `cloud-design-patterns`, `ddia-systems`, `release-it`, `platform-engineering`, `playwright`, `cloudiff-authentik-oidc`, `cloudiff-safe-release`, `cpp-pro`.

Referência por co-uso não cria dependência. Arestas ontológicas só existem com composição, referência, dependência operacional ou roteamento explícito comprovado.

## Aprendizado preexistente a preservar

As skills locais `cloudif-accessibility-audit`, `cloudif-api-tenant-security`, `cloudif-appsec-asvs`, `cloudif-disaster-security`, `cloudif-iam-authentik`, `cloudif-secure-release-gate`, `cloudif-security-observability`, `cloudif-threat-model`, `cloudif-ui-design-system` e `cloudif-ui-flow-tests` são fontes preexistentes de aprendizado. Elas não são descartadas nem promovidas automaticamente: seus requisitos são absorvidos semanticamente pela reconciliação e cada identidade só vira nó ontológico após versão, fonte, portão e procedência mecânicos.

## Migração V1 → V2

- V1 versionado é baseline funcional/visual e fonte de compatibilidade.
- V2 C++ é a direção tecnológica para serviços e lógica de produção.
- A reconciliação é aditiva antes de ser redutiva: nenhuma implementação antiga é removida até substituto C/C++ passar paridade funcional, segurança, observabilidade e rollback.
- Serviços/daemons Python são candidatos prioritários a C++23.
- Portal pode mover backend/controladores para C++, mas HTML/CSS/JS, navegação e comportamento visível permanecem equivalentes aos contratos congelados.
- Ferramentas e testes Python permanecem até existir verificação equivalente; linguagem não é justificativa para perder um gate.
- LegacyRetirement só executa depois de backup íntegro, substituição aceita e rollback comprovado.

## Gates mínimos por unidade C/C++

- namespace/manifesto/contrato/competência válidos;
- build CMake/Ninja/Clang em Debug e Release;
- `-Wall -Wextra -Wpedantic` sem warnings;
- ASan/UBSan limpos quando aplicável;
- CTest específico e integração real;
- paridade de autorização/tenant/CSRF/OIDC;
- falha/reconnect/retry quando distribuído;
- rollback real;
- para Portal: hashes/snapshots/DOM/fluxos congelados sem regressão visual.

## Autoverificação e autoconciliação

A skill administra somente o fecho CloudIFF: esta skill + `compoe` + `referencia` + dependências transitivas. Em alternância de unidade, confira deltas remotos, preserve aprendizado e só então avance referências. Nenhuma competência, prompt, catálogo ou projeção muda silenciosamente no meio de uma unidade.

## Estado inicial auditado

- V1 `debianlima/cloudiff@10a76d589525e4b4ee681f62274e585250d49429`: 1.320/1.320 arquivos auditados; sintaxe sem erros; validador oficial PASS.
- V2 local: núcleo C++23 e infraestrutura declarada em manifesto; união inicial V1↔V2 tem zero colisões de caminho.
- Plano de migração e hashes da interface ficam em `docs/reconciliation/`.
