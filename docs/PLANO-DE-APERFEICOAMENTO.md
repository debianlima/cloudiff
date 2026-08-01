# Plano de aperfeiçoamento — CloudIFF Portal

Documento de trabalho · versão 1 · 31/07/2026

Este plano parte de uma leitura do repositório `debianlima/cloudiff` no commit
`247ba90`. Ele não propõe reescrever a plataforma: o control-plane, o runtime e
o proxy funcionam e têm cobertura auditada. O alvo é **o Portal e a camada de
interface**, que é onde o custo de manutenção cresce mais rápido do que a
funcionalidade.

---

## 1. Diagnóstico

Cada item abaixo é observável no código atual. Nenhum é hipótese.

| # | Evidência | Onde | Consequência |
|---|-----------|------|--------------|
| 1 | Arquivo de 345 KB (~9 mil linhas) | `portal-current/cloudif-admin-portal.py` | Não é revisável em PR, não é testável em unidade, todo commit conflita |
| 2 | Arquivo de 123 KB | `mcp-gateway-current/cloudif-mcp-gateway.py` | Mesmo problema, num serviço que é superfície de integração |
| 3 | 19 camadas de CSS empilhadas por versão (`v70` … `v88`) | `cloudif_ui_components.py` | Ninguém sabe qual regra vence sem abrir o inspetor |
| 4 | `.cm-menu-tabs{display:none !important}` na camada v71 | idem, linha ~470 | A função `menu_tabs()` continua sendo chamada e renderizando HTML que o CSS esconde. Código morto que ainda custa CPU e confunde |
| 5 | Bloco `.acl-result-*` duplicado **byte a byte** nas camadas v87 e v88 | idem, final do arquivo | ~1,2 KB de CSS idêntico enviado duas vezes em cada resposta |
| 6 | `profile_mount()` definido **duas vezes** no mesmo arquivo | idem | A segunda definição sombreia a primeira em silêncio. A primeira é código morto |
| 7 | JS que varre `.card, .cm-card, .panel, .box, section, div` e esconde elementos por correspondência de texto (`'Usuário:'`, `'Grupos Authentik:'`) | `hideLooseUserBox()` | Um módulo escondendo a saída de outro por heurística de string. Quebra se um rótulo mudar |
| 8 | JS que esconde rodapés procurando `'uso didático'` e `'Instituto Federal Fluminense'` no texto | `footer()` | Mesmo padrão |
| 9 | Dois sistemas de botão (`.cm-btn` e `.btn`), dois de pílula, dois de cartão, dois de modal (`:target` e `.wizard`) | idem | Cada tela escolhe um. A interface parece dois produtos |
| 10 | ~40 usos de `!important` | idem | Sinal de que a cascata já não é usada, é vencida na força |
| 11 | CI executa apenas `validate.sh` (sintaxe + segredos). Nenhum teste roda | `.github/workflows/validate.yml` | O portão prova "isto faz parse", não "isto funciona" |
| 12 | `_tenant_level()` retorna no máximo `10`, mas `tenant.manage` exige `30` e `tenant.delete` exige `50` | `cloudif_rbac.py` | Essas ações são **inalcançáveis** fora do admin global. Metade do `ROLE_LEVEL` é código morto nesse caminho |
| 13 | `'domain admins'` no valor padrão de `CLOUDIF_ADMIN_GROUPS` | idem, linha 7 | Se a variável não for definida, todo Domain Admin do AD ganha admin global por omissão |
| 14 | `with sqlite3.connect(...)` sem `close()` | idem, `authorize()` e `explain()` | O context manager do `sqlite3` faz commit/rollback, não fecha. Acumula descritores num processo de longa duração que chama isso a cada request |
| 15 | Menu nomeado por tecnologia: "Git + Komodo", "Bancos / Tenants" | `menu_tabs()` | O usuário precisa saber como o sistema é construído para achar o que quer |

### O padrão por trás

Os itens 3 a 10 são o mesmo fenômeno: **correções aplicadas por acréscimo, nunca
por edição**. Cada versão empilhou uma camada nova para anular a anterior, em vez
de mudar a origem. É um modo de trabalho que funciona sob pressão e cobra juros
depois. O plano abaixo existe para pagar essa dívida uma vez e criar as condições
para que ela não volte.

---

## 2. Princípios

Cinco decisões que valem para todas as fases:

1. **Uma fonte de verdade por conceito.** Uma cor de sucesso, um botão primário,
   uma função de perfil. Se existem duas, uma está errada.
2. **A interface se descreve na linguagem de quem usa.** "Entrega", não "Git +
   Komodo". A pessoa gerencia publicações; que por baixo seja Komodo é detalhe
   de implementação.
3. **Nada é escondido por CSS ou por busca de texto.** Se não deve aparecer, não
   deve ser renderizado.
4. **Toda mudança entra por um portão que executa código**, não só que o compila.
5. **A migração é incremental e reversível.** Nenhuma fase exige parar a
   plataforma nem um corte único.

---

## 3. Fases

### Fase 0 — Rede de segurança
**Antes de tocar em qualquer linha de interface.**

- Ativar os testes existentes de `srv/cloudif/tests/` no workflow. Hoje eles
  estão no repositório e não rodam.
- Adicionar ao `validate-repository.py` três verificações novas, no mesmo estilo
  das que já existem:
  - **símbolo redefinido** no mesmo módulo (pega o item 6 automaticamente);
  - **bloco CSS duplicado** dentro do mesmo arquivo (pega o item 5);
  - **contagem de `!important`** com teto declarado, falhando se subir.
- Congelar o `cloudif_ui_components.py` atual como `legacy` e marcar no README
  que ele não recebe mais camadas novas.

O ganho aqui é que a partir daqui a regressão vira erro de CI, não descoberta em
produção.

---

### Fase 1 — Design system único

Substituir as 19 camadas por **três arquivos**:

```
portal/design/
  tokens.css       # cor, tipo, espaço, raio — a única fonte de valores
  base.css         # reset, tipografia, foco, acessibilidade
  components.css   # botão, chip, tabela, campo, painel, régua
```

Regras que o `validate.sh` passa a impor:

- nenhum literal de cor (`#hex`, `rgb(`) fora de `tokens.css`;
- nenhum `!important` em `components.css`;
- nenhum seletor com mais de duas classes encadeadas.

O protótipo `docs/portal-v2/portal-v2-prototipo.html` que acompanha este plano já
implementa esse sistema por inteiro e serve como referência executável. Ele mantém
o verde institucional `#168821` — que é o verde do padrão gov.br e faz sentido para
um Instituto Federal — mas o **reserva para dois usos apenas**: a marca e o estado
convergido. Hoje o mesmo verde pinta cabeçalho, botão, cabeçalho de tabela,
pílula, link e medidor; quando tudo é destaque, nada é.

Estados ganham cores próprias e semânticas: âmbar `#A8590B` para deriva, vermelho
`#9C1C24` para falha. O azul `#1B5FBF` é usado **só** no anel de foco, para nunca
competir com a leitura de estado.

**Tipografia.** Três papéis, três famílias:

| Papel | Família | Por quê |
|-------|---------|---------|
| Títulos | Bricolage Grotesque | Grotesca humanista, com personalidade; evita o ar de painel genérico |
| Texto | Public Sans | Desenhada para uso governamental, legível em corpo pequeno |
| Dados | JetBrains Mono | Versões, slugs, IDs, timestamps e estados alinham em coluna |

A escolha da monoespaçada para **dados de interface** — não só para código — é a
aposta deliberada deste redesenho. Um control plane é lido por quem vive em
terminal, e `v4.2.0` alinhado sob `v4.1.0` comunica a diferença antes de qualquer
rótulo.

---

### Fase 2 — Quebra do monólito

Estrutura alvo para o Portal:

```
portal/
├── app.py                  # bootstrap e roteamento — fino, sem regra de negócio
├── registry.py             # registro de módulos → navegação gerada
├── core/
│   ├── auth.py             # sessão e identidade
│   ├── rbac.py             # autorização (movido de lib/, ver Fase 4)
│   ├── http.py             # helpers de request/response
│   └── errors.py           # páginas de erro e estado vazio
├── design/
│   ├── tokens.css
│   ├── base.css
│   ├── components.css
│   └── app.js
├── ui/
│   ├── shell.py            # sidebar, barra superior, rodapé
│   ├── components.py       # botão, chip, tabela, campo — API única
│   └── icons.py
└── modules/
    ├── overview/
    ├── projects/
    ├── environments/
    ├── data/
    ├── delivery/
    ├── health/
    └── admin/
```

Cada módulo tem sempre os mesmos quatro arquivos:

```
modules/projects/
├── __init__.py     # declara o módulo ao registry
├── routes.py       # caminhos → funções
├── views.py        # monta HTML usando ui/components.py
└── service.py      # regra de negócio e acesso a dados
```

**A peça que faz isso escalar é o `registry.py`.** Cada módulo declara sua
própria entrada de navegação, permissão exigida e rotas. A barra lateral é
**gerada** a partir desse registro, filtrada pelo RBAC do usuário. Não existe
mais uma função `menu_tabs()` com a lista escrita à mão — adicionar um módulo
passa a adicionar o item de menu automaticamente, já com controle de acesso.

**Ordem de extração** (do mais isolado para o mais acoplado, para que cada passo
seja pequeno e reversível):

1. `health` — já tem painéis próprios (`cloudif_reconcile_panel`, monitor)
2. `admin` — ACL e AD já vivem em módulos separados
3. `data` — bancos e tenants
4. `delivery` — Git/Komodo
5. `environments` — os executores de preview/homologação/produção
6. `projects` — o maior, e o que mais se beneficia de ir por último
7. `overview` — depende de todos, então fecha a fila

---

### Fase 3 — Nova organização dos menus

De 7 itens planos e de níveis misturados para 7 grupos por intenção:

| Hoje | Proposto |
|------|----------|
| Resumo | **Início** |
| Projetos | **Projetos** → Todos os projetos · Publicações · Aprovações |
| — | **Ambientes** → Pré-visualização · Homologação · Produção |
| Bancos / Tenants | **Dados** → Bancos de dados · Tenants |
| Git + Komodo | **Entrega** → Repositórios · Compilações · Implantações |
| Verificação e reparação | **Saúde** → Servidores · Reconciliação · Auditoria |
| Administração | **Administração** → Pessoas e acessos · Políticas · Configuração |
| Ajuda | rodapé da barra lateral |

Três correções concretas:

- **"Bancos / Tenants" era um rótulo com dois modelos mentais.** Virou dois itens
  dentro de um grupo.
- **"Git + Komodo" nomeava fornecedores.** Virou "Entrega", com as três coisas
  que a pessoa realmente faz ali.
- **"Verificação e reparação" descrevia a ferramenta.** Virou "Saúde", que
  descreve o assunto.

O ganho de escala: os 23 serviços do control-plane cabem nesses grupos sem criar
nenhum item de primeiro nível novo.

---

### Fase 4 — Autorização

Não é interface, mas é o arquivo que um auditor abre primeiro e precisa entrar
neste ciclo.

1. **Decidir o caso do item 12.** Se apenas o admin global gerencia tenants, isso
   deve estar escrito no código, não emergir de um teto silencioso em
   `_tenant_level`. Se não é o caso, é um bug de permissão.
2. **Tirar `'domain admins'` do padrão.** Deixar a lista padrão vazia e falhar
   ruidosamente se `CLOUDIF_ADMIN_GROUPS` não estiver definida. Concessão de
   privilégio por omissão é o tipo de coisa que sobrevive despercebida por anos.
3. **Fechar a conexão** — `contextlib.closing` ou uma conexão por request
   gerenciada pelo `core/http.py`.
4. **Reformatar o arquivo.** `import os, sqlite3`, vários comandos por linha e
   ausência de espaço em volta de `=` são aceitáveis em muitos lugares; num
   arquivo de decisão de acesso, legibilidade é requisito de segurança.
5. **Cobrir com testes de tabela**: para cada par (papel, ação), o resultado
   esperado. É o teste mais barato de escrever e o de maior retorno em todo o
   repositório.

---

### Fase 5 — Escala

Só depois das anteriores, e apenas se a necessidade aparecer:

- **SQLite → PostgreSQL** no caminho de autorização, se a concorrência do Portal
  crescer. Hoje é uma conexão nova por chamada de `authorize()`.
- **API separada da renderização.** Com os módulos já isolados, expor
  `service.py` como JSON é incremental, e abre caminho para um front desacoplado
  se um dia isso fizer sentido. Não é necessário agora, e fazer antes da Fase 2
  seria construir sobre o monólito.
- **Detector de deriva no CI.** O `COVERAGE_AUDIT.json` é uma foto de um momento.
  Um job periódico comparando repositório × hosts transforma isso em sinal
  contínuo.

---

## 4. O que não fazer

- **Não reescrever tudo em React agora.** O problema do Portal não é a tecnologia
  de renderização; é a ausência de fronteiras entre módulos. Trocar o motor sem
  resolver isso reproduz o mesmo emaranhado em outra linguagem.
- **Não migrar os três nós na mesma janela.** As fases foram desenhadas para o
  Portal. O runtime e o proxy só entram depois que o padrão estiver provado.
- **Não apagar o `legacy`.** Ele fica lado a lado durante toda a migração, como
  descrito no guia que acompanha este plano.

---

## 5. Sequência sugerida

| Fase | Escopo | Depende de |
|------|--------|-----------|
| 0 | Testes no CI, novas verificações no validate, congelar legacy | — |
| 1 | tokens/base/components, protótipo virando código | 0 |
| 2 | registry + extração dos 7 módulos, um por vez | 1 |
| 3 | Navegação gerada, novos rótulos | 2 |
| 4 | RBAC: correção, testes, reformatação | 0 |
| 5 | Postgres, API, detector de deriva | 2, 4 |

A Fase 4 é paralela às demais — depende só da Fase 0 e pode andar em outra
frente.

---

## Anexos

- `docs/portal-v2/portal-v2-prototipo.html` — implementação de referência do design
  system e da nova navegação. Abre em qualquer navegador, sem build.
- `docs/GUIA-DE-MIGRACAO.md` — como sair da versão atual, como os módulos funcionam
  e como a nova estrutura se organiza.
