# CloudIFF — padrão de PHP, Node.js e Terminal por estágio

Data de consolidação: 23/11/2026.

## Objetivo

As ferramentas **PHP**, **Node.js** e **Terminal** do Portal devem inspecionar exatamente o runtime do projeto/estágio selecionado, sem adivinhar nomes de serviço, sem cair em container de outro projeto e sem recriar URL, container ou deployment apenas para diagnóstico.

Contrato:

```text
Projeto selecionado
  + estágio selecionado (Wn / Hn / Pn)
  + identidade do runtime real
        ↓
PHP / Node.js / Terminal
```

A mesma identidade de estágio deve alimentar as três ferramentas.

## Regra de identidade

A resolução nunca pode assumir globalmente nomes como `api`, `web`, `app`, `W1` ou `W3`.

A ordem é:

1. `release_flow_status()` / read-model identifica o estágio do projeto;
2. Preview consulta a identidade real do stack/runtime daquele projeto;
3. H/P Compose usam o `deploymentId` real e o inventário de `services/routes` do Executor;
4. runtime composto usa o par exato de containers do stage;
5. Produção legada usa o container versionado exato da P ativa;
6. Komodo revalida projeto, stage/deployment/stack e container antes de executar diagnóstico ou abrir terminal.

## Preview linked-compose

O Portal usa `_linked_compose_status()` e recebe:

- `stageCode` real;
- `stackId` real;
- container real reportado pelo stack;
- serviço real retornado por `ListStackServices`.

Exemplo validado:

- LabHardware: W1, serviço `app`, container `lab_hardware_app`;
- Agenda Única: W3, serviço `api`, container `cloudif-agenda-unica-api-1`.

**W3 não é regra global.** Agenda permanece W3 porque esse é o slot real dela. LabHardware permanece W1 enquanto esse for seu slot real. Recriar/reconciliar runtime não pode copiar o Wn de outro projeto nem renumerar Preview por conveniência.

## Preview genérico

Para runtimes genéricos, usa-se o container retornado por `preview_status()`.

Exemplos validados:

- SilviPro W1 → `cloudif-p1002-preview-web`;
- CPUHub W1 → `cloudif-p1021-preview-web`;
- Cadales W1 → `cloudif-p1022-preview-web`.

O diagnóstico não inventa `-api-1` ou `-web-1` quando esses nomes não existem.

## Preview composto

Quando existir o par numerado do mesmo estágio:

- `cloudif-p<NUM>-w<N>-preview-app`;
- `cloudif-p<NUM>-w<N>-preview-web`;

o `app` é priorizado para PHP/Node/Terminal.

O Komodo valida:

- nome exato do app;
- bridge `web` do mesmo Wn;
- ambos running;
- label `org.cloudiff.project`;
- stage permitido `preview|restored-candidate`;
- servidor real antes de criar terminal.

Exemplo validado: Paperclip W1.

Essa regra **não remove** o bloqueio de Homologação do Paperclip: H continua bloqueada enquanto o runtime composto não possuir manifest completo para app/gateway/volume.

## H/P Compose

Para `compose-snapshot`, o Portal não deriva mais `-api`, `-web` ou qualquer outro nome.

Ele consulta o Executor e obtém `services` e `routes` do deployment. O resolver:

- prioriza serviço roteado;
- evita escolher DB como primeira opção de aplicação;
- mantém lista completa para PHP/Node;
- envia `container_candidates` e `service_candidates` ao Komodo;
- Komodo exige labels `org.cloudiff.deployment` e `org.cloudiff.project` corretas.

Terminal só abre se `(container, service)` pertencer ao deployment selecionado.

Promoção H→P continua usando a mesma instância; as ferramentas apenas interrogam essa identidade e nunca a recriam.

## Produção legada

Produção histórica/legada não deve ser falsamente marcada como same-instance.

Para inspeção, porém, PHP/Node/Terminal usam o container versionado real:

`cloudif-p<NUM>-p<PUBLICATION>-publication-web`

Terminal valida antes:

- P está registrada como `ready` e `is_active=1` no agente;
- nome do container corresponde exatamente à P selecionada;
- container está running/healthy;
- servidor do projeto existe.

Exemplos validados:

- SilviPro P1;
- CPUHub P5;
- Cadales P2.

## PHP e Node.js

Ausência do runtime não é falha do painel.

Se PHP/Node não estiver instalado no estágio:

- `ok=true`;
- `available=false`;
- listar containers/serviços do estágio;
- informar explicitamente que a linguagem não está instalada;
- mostrar versões de runtimes encontrados quando possível.

Não instalar pacote automaticamente para “fazer o painel funcionar”. Se o usuário instalar manualmente uma versão dentro do Preview real, essa alteração pertence ao runtime do Preview e será capturada pelo mecanismo de snapshot/clonagem aplicável ao projeto quando H for criada.

## Terminal

Terminal é uma ferramenta de inspeção do runtime selecionado, não um provisionador.

Nunca deve:

- criar novo W/H/P;
- recriar container só para abrir shell;
- trocar URL;
- usar container de outro stage;
- usar nome derivado sem validar contra stack/deployment;
- contornar ACL/ownership.

Criar a sessão/terminal do Komodo para um container já existente é permitido; isso não recria o runtime.

## Variáveis

As variáveis continuam sendo por estágio. O painel de variáveis deve usar o mesmo `project + stageCode` da seleção.

No LabHardware, a auditoria de 23/11/2026 não conseguiu exercitar edição/propagação porque não havia variável de aplicação configurada. Isso não autoriza criar variável artificial apenas para teste.

Quando houver variável real:

- edição afeta somente o estágio selecionado;
- W→H carrega o estado aprovado do Preview;
- H→P mantém o estado da mesma instância;
- read-model deve ser invalidado/atualizado após mudança.

## Prova LabHardware

Estado validado:

- Preview W1;
- Produção P14;
- Preview PHP: PHP 8.2.35 no `lab_hardware_app`;
- Preview Node.js: não instalado, exibido como `available=false`;
- Preview Terminal: `lab_hardware_app`, serviço `app`;
- Produção PHP: `cloudif-dep-25a4c2f4b979a414f92153a6-app`;
- Produção Node.js: não instalado, sem erro de painel;
- Produção Terminal: mesmo container `app` do deployment P14.

Os seis IDs observados antes da correção foram comparados depois e permaneceram **idênticos**. Nenhum container do LabHardware foi recriado.

URLs preservadas:

- `1001-w1-preview.cloudiff.duckdns.org`;
- `1001-p14-publication.cloudiff.duckdns.org`;
- `1001.cloudiff.duckdns.org`;
- `labhard.cloudiff.duckdns.org`.

## Matriz global validada

Previews modernos com PHP/Node/Terminal sem erro de contrato:

- LabHardware W1;
- SilviPro W1;
- Agenda Única W3;
- CPUHub W1;
- Cadales W1;
- Paperclip W1;
- SGREP v2 W1.

Produções ativas validadas:

- LabHardware P14;
- SilviPro P1;
- Agenda Única P11;
- CPUHub P5;
- Cadales P2.

## Registros legados sem ACL moderna

Os IDs abaixo possuem registro público/Preview histórico, mas não possuem linha moderna suficiente em `projects`/ACL para autorizar as ferramentas:

- 1007 `silvipro-jt-2026`;
- 1010 `teste-sofa`;
- 1014 `grupix`;
- 1018 `testando123`;
- 1019 `hardness-e2e-0254`;
- 1023 `isha`;
- 1024 `mvplanner`.

Eles **não devem** receber Terminal por bypass de permissão. A migração exige confirmar owner/finalidade e criar/reconciliar o registro moderno explicitamente.

## Gate para novo release

Antes de considerar um projeto pronto para teste humano H→P→exclusão:

1. Preview real responde;
2. PHP/Node resolvem o estágio ou informam ausência sem erro;
3. Terminal resolve container/serviço real do estágio;
4. criar H usa o Preview selecionado do próprio projeto;
5. H usa inventário real do deployment;
6. promover H→P mantém o mesmo deployment/container;
7. P anterior fica realmente offline antes de ser mostrada como Offline;
8. exclusão de P histórica nunca atinge P ativa;
9. read-model é atualizado em cada mutação;
10. URLs e IDs de runtimes não relacionados permanecem inalterados.

## Referências

- `docs/PADRAO-CLOUDIFF-PREVIEW-HOMOLOGACAO-PRODUCAO-20261120.md`;
- `docs/RUNBOOK-PADRAO-CLOUDIFF-WHP-CONTINUIDADE.md`;
- `docs/PADRAO-CLOUDIFF-INDICE-READMODEL-PORTAL-20261122.md`;
- `docs/AUDITORIA-GLOBAL-PROJETOS-WHP-20261122.md`.
