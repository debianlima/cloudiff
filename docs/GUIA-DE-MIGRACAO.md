# Guia de migração e arquitetura — Portal CloudIFF v2

Para quem vai manter, migrar ou estender o Portal.

Se você chegou agora ao projeto, leia as seções 1 e 2 e pule direto para a 5
(criar um módulo). Se você mantém a versão atual em produção, comece pela 3.

---

## 1. O que muda, em uma tela

A v1 é **um arquivo grande que faz tudo**. A v2 é **um esqueleto fino com
módulos plugáveis**.

```
v1                                    v2
────────────────────────────          ────────────────────────────
cloudif-admin-portal.py  345 KB       app.py                  ~4 KB
  └ tudo                              registry.py             ~3 KB
                                      core/       (4 arquivos)
cloudif_ui_components.py  27 KB       design/     (3 CSS + 1 JS)
  └ 10 camadas v70…v88                ui/         (3 arquivos)
cloudif_ui_pages.py       96 KB       modules/    (7 módulos × 4 arquivos)
  └ render_tab(tab, user)
```

Três diferenças que importam mais que o tamanho:

**A navegação deixa de ser escrita à mão.** Na v1, `menu_tabs()` tem a lista de
abas dentro dela. Na v2, cada módulo declara sua entrada e o menu é montado a
partir disso, já filtrado pela permissão do usuário.

**O CSS deixa de ser empilhado.** Na v1, corrigir algo significava acrescentar
uma camada `/* CloudIF v89 */` no fim do arquivo. Na v2, você edita o token ou o
componente. Se precisar de `!important`, o CI reprova.

**Nada é escondido depois de renderizado.** A v1 tem JavaScript que procura
elementos pelo texto (`'Usuário:'`, `'uso didático'`) e os esconde. Na v2, se
não deve aparecer, o módulo não renderiza.

---

## 2. A estrutura nova

```
portal/
├── app.py                  Sobe o servidor, registra módulos, roteia. Fino.
├── registry.py             Onde os módulos se anunciam. Gera a navegação.
│
├── core/
│   ├── auth.py             Quem é a pessoa (sessão, Authentik, grupos AD)
│   ├── rbac.py             O que ela pode fazer
│   ├── http.py             Request, response, conexão de banco por requisição
│   └── errors.py           Erro e estado vazio, com texto que orienta
│
├── design/
│   ├── tokens.css          ÚNICO lugar com valor de cor, tipo, espaço
│   ├── base.css            Reset, tipografia, foco visível
│   ├── components.css      Botão, chip, tabela, campo, painel, régua
│   └── app.js              Comportamento do esqueleto (menu, atalhos)
│
├── ui/
│   ├── shell.py            Barra lateral, barra superior, rodapé
│   ├── components.py       btn(), chip(), table(), field(), panel()
│   └── icons.py            SVGs inline, um por nome
│
└── modules/
    ├── overview/           Início
    ├── projects/           Projetos, publicações, aprovações
    ├── environments/       Pré-visualização, homologação, produção
    ├── data/               Bancos de dados, tenants
    ├── delivery/           Repositórios, compilações, implantações
    ├── health/             Servidores, reconciliação, auditoria
    └── admin/              Pessoas e acessos, políticas, configuração
```

### A regra de dependência

```
modules/  →  ui/  →  design/
    │         │
    └────→ core/
```

Setas apontam só para a direita e para baixo. Na prática:

- um módulo **pode** importar de `core/` e de `ui/`;
- um módulo **não pode** importar de outro módulo;
- `ui/` **não pode** importar de `modules/`;
- `core/` não importa de ninguém acima dele.

Se dois módulos precisam da mesma coisa, ela sobe para `core/` ou `ui/`. É
essa regra que impede a v2 de virar a v1 de novo.

---

## 3. Como migrar sem parar a plataforma

A migração é por **coexistência**: v1 e v2 rodam lado a lado, e as rotas passam
uma a uma. Ninguém precisa de uma janela de corte.

### 3.1 Preparar

```bash
git checkout -b portal-v2
mkdir -p portal/{core,design,ui,modules}
```

**Antes de copiar, decida qual árvore é a fonte.** O repositório tem duas:
`srv/cloudif/lib/` e `srv/cloudif/staging/lib/`. Dos 25 arquivos, 20 têm blob
SHA idêntico e 5 divergem:

| Arquivo | `lib/` | `staging/lib/` |
|---|---:|---:|
| `cloudif_portal_publications.py` | 11.960 | 8.227 |
| `cloudif_project_provision_worker.py` | 3.367 | 2.109 |
| `cloudif_reconcile_client.py` | 8.777 | 6.725 |
| `cloudif_project_action_safe.py` | 14.350 | 14.026 |
| `cloudif_ui_publications.py` | 4.258 | 4.235 |

Nenhum manifesto diz qual vence. Enquanto isso não estiver resolvido, o
`portal/legacy/` nasce ambíguo e a comparação lado a lado do passo 3.3 não tem
referência confiável. Resolva primeiro; é trabalho de uma tarde e evita
descobrir a divergência no meio da migração.

Feita a escolha, copie sem alterar nada:

```bash
mkdir -p portal/legacy
cp components/control-plane/current-apps/portal-current/*.py portal/legacy/
```

`portal/legacy/` é intocável durante toda a migração. Ele é a sua rede.

### 3.2 Ligar o desvio

Em `app.py`, toda rota que a v2 ainda não conhece cai no legado:

```python
# app.py
from registry import registry
from portal.legacy import cloudif_admin_portal as legacy

def handle(request):
    module = registry.match(request.path)

    if module is None:
        return legacy.handle(request)      # nada migrado ainda: tudo cai aqui

    return module.dispatch(request)
```

No primeiro dia, `registry` está vazio e **100% do tráfego vai para o legado**.
A v2 está no ar sem mudar nada para o usuário.

### 3.3 Migrar um módulo por vez

A ordem recomendada — do mais isolado para o mais acoplado:

| Ordem | Módulo | Por quê primeiro |
|-------|--------|------------------|
| 1 | `health` | Já tem painéis próprios; poucas dependências |
| 2 | `admin` | ACL e AD já vivem em módulos separados na v1 |
| 3 | `data` | Bancos e tenants têm fronteira clara |
| 4 | `delivery` | Git/Komodo é volumoso mas coeso |
| 5 | `environments` | Depende dos executores do runtime |
| 6 | `projects` | O maior; ganha mais indo por último |
| 7 | `overview` | Consome todos os outros; fecha a fila |

Para cada módulo, o ciclo é:

1. criar os quatro arquivos (seção 5);
2. registrar no `registry`;
3. verificar que a rota antiga passou a cair na v2;
4. **comparar as duas telas lado a lado** antes de seguir;
5. commit.

Se algo der errado, remova o registro. O desvio devolve a rota ao legado na
hora — sem redeploy, sem rollback de banco.

### 3.4 Encerrar

Quando `registry.match()` nunca mais devolver `None` em uma semana de tráfego
real, `portal/legacy/` pode sair. Só então.

```bash
git rm -r portal/legacy
```

### 3.5 O que **não** migrar junto

`.env`, políticas JSON, bancos, unidades systemd e os agentes do runtime e do
proxy **não mudam**. A v2 é uma reorganização do Portal, não da plataforma. As
unidades continuam apontando para o mesmo caminho em
`/srv/cloudif/app-pointers/portal-current` — o que muda é o que existe dentro
dele.

---

## 4. O registry, em detalhe

É a peça central. Cada módulo se anuncia com quatro informações:

```python
# registry.py
from dataclasses import dataclass, field
from typing import Callable

@dataclass
class NavItem:
    label: str            # o que a pessoa lê
    path: str             # a rota
    icon: str             # nome em ui/icons.py
    permission: str       # ação exigida, validada por core/rbac.py
    badge: Callable | None = None   # opcional: contador ao lado do item

@dataclass
class Module:
    key: str
    group: str            # rótulo do grupo na barra lateral
    order: int            # posição do grupo
    nav: list[NavItem] = field(default_factory=list)
    routes: dict = field(default_factory=dict)
```

E a navegação sai pronta, já filtrada:

```python
def navigation_for(user):
    """Monta a barra lateral com o que este usuário pode ver."""
    groups = {}

    for module in sorted(_modules.values(), key=lambda m: m.order):
        visible = [
            item for item in module.nav
            if rbac.authorize(user, item.permission)
        ]
        if visible:
            groups.setdefault(module.group, []).extend(visible)

    return groups
```

**A consequência prática:** um item de menu que a pessoa não pode usar não é
renderizado desabilitado — ele simplesmente não existe naquela sessão. Some o
conceito de "botão cinza que não faz nada", que hoje ocupa `.cm-disabled` em
vários lugares da v1.

---

## 5. Como criar um módulo

Exemplo completo, o módulo `data` (Bancos de dados e Tenants).

### `modules/data/__init__.py`

```python
from registry import Module, NavItem, register
from . import routes

register(Module(
    key="data",
    group="Dados",
    order=40,
    nav=[
        NavItem(
            label="Bancos de dados",
            path="/dados/bancos",
            icon="database",
            permission="tenant.view",
        ),
        NavItem(
            label="Tenants",
            path="/dados/tenants",
            icon="tenants",
            permission="tenant.view",
            badge=lambda user: routes.tenant_count(user),
        ),
    ],
    routes=routes.table,
))
```

### `modules/data/routes.py`

```python
from core.http import page, require
from . import views, service

@require("tenant.view")
def databases(request):
    data = service.list_databases(request.user)
    return page(request, views.databases(data))

@require("tenant.manage")
def create_tenant(request):
    tenant = service.create_tenant(request.user, request.form["slug"])
    return page(request, views.tenant_created(tenant))

table = {
    "/dados/bancos":   databases,
    "/dados/tenants":  tenants,
    "/dados/tenants/novo": create_tenant,
}
```

O decorador `@require` chama `core/rbac.py`. **Nenhuma view checa permissão por
conta própria** — é sempre na borda, uma vez, de forma auditável.

### `modules/data/views.py`

```python
from ui.components import panel, table, btn, chip

def databases(rows):
    return panel(
        title="Bancos de dados",
        action=btn("Criar banco", href="/dados/bancos/novo"),
        body=table(
            columns=["Nome", "Tenant", "Tamanho", "Estado"],
            rows=[
                [r.name, r.tenant, r.size_human, chip(r.state)]
                for r in rows
            ],
        ),
    )
```

Views **só montam HTML**. Não consultam banco, não decidem permissão, não
formatam regra de negócio. Se uma view tem `if`, provavelmente esse `if`
pertence ao `service.py`.

### `modules/data/service.py`

```python
from core.http import db

def list_databases(user):
    with db() as con:
        return [
            Database(**row)
            for row in con.execute(SELECT_DATABASES, (user.tenant_scope,))
        ]
```

Toda a regra de negócio e todo o acesso a dados moram aqui. É o único arquivo
do módulo que precisa de teste de unidade — e é o mais fácil de testar,
justamente porque não renderiza nada.

### Resumindo o contrato

| Arquivo | Pode | Não pode |
|---------|------|----------|
| `__init__.py` | declarar nav e rotas | conter lógica |
| `routes.py` | orquestrar, exigir permissão | montar HTML, consultar banco |
| `views.py` | montar HTML via `ui/` | consultar banco, decidir permissão |
| `service.py` | regra de negócio, dados | gerar HTML |

---

## 6. Como usar o design system

### Nunca escreva um valor de cor fora de `tokens.css`

```css
/* errado — vai reprovar no CI */
.minha-coisa{ color:#168821; }

/* certo */
.minha-coisa{ color:var(--iff); }
```

### Os tokens de estado têm significado fixo

| Token | Significa | Use quando |
|-------|-----------|------------|
| `--iff` | Convergido, institucional | O estado real bate com o declarado |
| `--drift` | Deriva, pendência | Diverge, mas o serviço responde |
| `--halt` | Falha, bloqueio | Não responde ou foi barrado |
| `--focus` | Foco de teclado | **Só** para `:focus-visible`. Nunca decorativo |

Não use `--iff` para "coisa boa genérica". O verde tem um significado técnico
nesta interface: **o observado é igual ao declarado**. Se você pintar de verde
um botão qualquer, quebra a leitura de estado da tela inteira.

### Todo par texto/fundo precisa de 4,5:1

Sendo um site de instituição federal, o eMAG e a Lei Brasileira de Inclusão
exigem contraste AA. O CI verifica, e vale saber que a primeira versão deste
próprio protótipo reprovou: `--ink-3` estava em `#6B7D71`, que dá 4,07:1 sobre
`--paper`. Foi corrigido para `#5E6E63` (5,02:1).

Se você criar um token de cor novo, calcule o contraste contra `--paper` **e**
contra `--surface` — a diferença entre os dois é pequena, mas foi ela que
separou o reprovado do aprovado nesse caso.

### A régua de reconciliação

É o elemento de assinatura da v2. Sempre que existir um par
declarado/observado, use-o em vez de um selo único:

```html
<div class="row">
  <div class="row-name">
    <div class="row-service">npm-publisher-agent</div>
    <div class="row-node">proxy</div>
  </div>
  <div class="state is-live">v4.2.0</div>
  <div class="link is-drift">
    <span class="link-tag">atrás 1 versão</span>
  </div>
  <div class="state is-off">v4.1.0</div>
  <div class="row-act">
    <a class="btn btn-alert btn-sm" href="#">Reconciliar</a>
  </div>
</div>
```

A linha entre os dois estados é **sólida** quando convergem e **tracejada**
quando divergem. O rótulo no meio diz a distância, não só que existe diferença.

### Como escrever os textos

Regras curtas, tiradas do que já dá problema na v1:

- **Nomeie pelo que a pessoa controla**, não pela implementação. "Implantações",
  não "Komodo stacks".
- **A ação mantém o nome do início ao fim.** O botão diz "Publicar", o aviso de
  sucesso diz "Publicado". Nunca "Enviar" → "Operação concluída".
- **Erro explica o que houve e o que fazer.** Sem pedir desculpas e sem ser
  vago. "O proxy está servindo a v4.1.0; a versão declarada é 4.2.0" é melhor
  que "Falha de sincronização".
- **Tela vazia é convite.** "Nenhum tenant ainda. Crie o primeiro para começar."
  Não "Sem dados".

---

## 7. Perguntas frequentes

**Posso adicionar uma aba nova sem mexer no menu?**
Sim — é o ponto. Declare o `NavItem` no `__init__.py` do módulo. A barra lateral
se atualiza sozinha, respeitando a permissão.

**Onde ponho algo que dois módulos usam?**
Se é visual, em `ui/components.py`. Se é regra, em `core/`. Nunca importe um
módulo de dentro de outro — quando você sentir vontade, é sinal de que a peça
subiu de nível.

**E o `render_tab(tab, user)` da v1?**
Ele sai junto com `portal/legacy/`, no fim da migração. Enquanto existir, é
chamado pelo desvio do `app.py` e não deve receber código novo.

**Preciso de build, npm, bundler?**
Não. O `design/` é CSS e JS servidos direto, como na v1. A escolha é
deliberada: adicionar cadeia de build ao Portal traria uma classe de problema
que a plataforma hoje não tem.

**Como testo um módulo?**
`service.py` com teste de unidade comum; `routes.py` com um teste por
permissão — a tabela (papel, ação, esperado) da Fase 4 do plano. `views.py`
raramente precisa de teste; se precisar, é sinal de que tem lógica no lugar
errado.

**Como reverto se um módulo migrado der problema?**
Remova a chamada `register(...)` do `__init__.py` dele. O desvio em `app.py`
devolve as rotas ao legado imediatamente.

---

## 8. Antes de abrir o PR

```bash
scripts/validate.sh
```

Além do que a v1 já verificava, o portão passa a reprovar:

- valor de cor literal fora de `tokens.css`;
- `!important` em `components.css`;
- par texto/fundo abaixo de 4,5:1;
- import entre módulos irmãos;
- símbolo redefinido no mesmo arquivo;
- bloco CSS duplicado;
- divergência não declarada entre `lib/` e `staging/lib/`;
- rota registrada sem `permission` declarada.

E, diferente da v1, os testes de `srv/cloudif/tests/` rodam de verdade.

---

## Referências

- `docs/PLANO-DE-APERFEICOAMENTO.md` — o diagnóstico e o porquê de cada fase
- `docs/portal-v2/portal-v2-prototipo.html` — o design system implementado, sem build
- `docs/ARCHITECTURE.md` — os três nós da plataforma
- `docs/MAINTENANCE.md` — promoção para produção e rollback
