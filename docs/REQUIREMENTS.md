# Requisitos de execução — Portal CloudIFF v2

Versão 1 · 01/08/2026

Este documento diz **o que precisa ser construído** no Portal v2 e **como saber
que ficou pronto**. Ele não repete o porquê — isso está em
`docs/PLANO-DE-APERFEICOAMENTO.md` — nem o como estrutural, que está em
`docs/GUIA-DE-MIGRACAO.md`.

Todo número aqui foi extraído do código da v1 em execução no control-plane, não
estimado.

---

## 1. Escopo

**Dentro:** as 31 rotas servidas hoje por `cloudif-admin-portal.py` (5.735
linhas, 164 funções), reorganizadas nos 7 módulos da v2.

**Fora:** runtime, proxy, agentes, templates de tenant, unidades systemd e
esquema de banco. A v2 reorganiza o Portal, não a plataforma.

**Invariante:** nenhuma rota pode mudar de endereço, de método ou de resposta
durante a migração. A v2 é uma troca de implementação, não de contrato.

---

## 2. Inventário a converter

31 rotas, agrupadas por natureza:

### 2.1 Páginas (4)

| Rota | Módulo destino |
|---|---|
| `/cloudiff/portal` | `overview` |
| `/cloudiff/portal/control` | `health` |
| `/cloudiff/portal/control/` | `health` |
| `/cloudiff/portal/repair-dashboard` | `health` |

### 2.2 Ações — alteram estado, exigem CSRF (12)

| Rota | Módulo destino |
|---|---|
| `/action/project_action` | `projects` |
| `/action/publication` | `projects` |
| `/action/repair-project` | `health` |
| `/action/rotate-project-credential` | `admin` |
| `/action/open-project-terminal` | `delivery` |
| `/action/production-window-schedule` | `environments` |
| `/action/production-window-cancel` | `environments` |
| `/action/production-alert-ack` | `environments` |
| `/action/production-incident-assign` | `environments` |
| `/action/production-incident-escalate` | `environments` |
| `/action/production-incident-mitigate` | `environments` |
| `/action/production-incident-close` | `environments` |

### 2.3 APIs — leitura (13)

| Rota | Módulo destino |
|---|---|
| `/api/navigation` | `core` (shell, não é módulo) |
| `/api/approvals` | `projects` |
| `/api/publication` | `projects` |
| `/api/promotions` | `delivery` |
| `/api/project-capabilities` | `projects` |
| `/api/project-identities` | `projects` |
| `/api/agia-lifecycle` | `projects` |
| `/api/transactions` | `health` |
| `/api/reconciliation` | `health` |
| `/api/repair-dashboard` | `health` |
| `/control/api/dashboard` | `health` |
| `/api/production-operations` | `environments` |
| `/api/agent-guide` | `admin` |

### 2.4 Internas — sem sessão de usuário (2)

| Rota | Módulo destino |
|---|---|
| `/cloudiff/internal/access-ingest` | `core` (autenticação por token, não por grupo) |
| `/cloudiff/internal/access-latest` | `core` |

### 2.5 Distribuição resultante

| Módulo | Rotas | Observação |
|---|---:|---|
| `health` | 8 | Maior conjunto; já tem painéis próprios na v1 |
| `environments` | 8 | Todas as operações de produção |
| `projects` | 7 | O mais acoplado ao restante |
| `admin` | 2 | Pequeno, bom para validar o padrão |
| `delivery` | 2 | — |
| `overview` | 1 | Consome todos os outros |
| `data` | 0 | **Sem rota própria hoje**; ver §6 |
| `core` | 3 | Shell e rotas internas |

---

## 3. O que exige mais atenção: o modelo de permissão

Este é o requisito mais delicado do projeto.

**A v1 não tem autorização centralizada.** Medição no arquivo:

| Padrão | Ocorrências |
|---|---:|
| `authorize()` / `rbac.` | **0** |
| Comparação inline de grupo | 155 |
| `is_admin` | 19 |
| `403` / `forbidden` | 59 |
| Referências a CSRF | 92 |

Existem apenas **três grupos** citados literalmente:

| Grupo | Ocorrências | Papel presumido |
|---|---:|---|
| `CloudIF-Tenants` | 22 | Usuário comum (aluno) |
| `CloudIF-Professor` | 16 | Professor |
| `CloudIF-Tenants-Admin` | 18 | Administrador |

E há **dois helpers de versões diferentes coexistindo** no mesmo arquivo:

```python
1303: is_admin = cloudif_v56_is_admin(self.headers)
1340: is_admin = cloudif_v54_is_admin(self.headers)
```

### 3.1 Requisito R-PERM-1 — levantar antes de converter

Antes de escrever qualquer módulo, produzir a tabela

```
(rota, método, grupo, decisão observada na v1)
```

para as 31 rotas × 3 grupos = **93 combinações**. Extração do código, não
suposição.

### 3.2 Requisito R-PERM-2 — reconciliar v54 × v56

Comparar `cloudif_v54_is_admin` e `cloudif_v56_is_admin`. Se divergirem em
algum caso, isso é um bug de autorização em produção hoje, e a decisão de qual
vence precisa ser registrada antes da conversão.

### 3.3 Requisito R-PERM-3 — permissões nomeadas

Traduzir a tabela para nomes usados em `@require(...)`. Nomenclatura:
`<recurso>.<ação>` — por exemplo `project.view`, `project.publish`,
`tenant.manage`, `production.window.schedule`, `credential.rotate`.

**A tabela do R-PERM-1 é a especificação de aceite.** Para cada uma das 93
combinações, a v2 deve decidir igual à v1. Divergência é reprovação, mesmo que
a v2 pareça "mais correta" — mudança de política é decisão separada, tomada
depois e de forma explícita.

### 3.4 Requisito R-PERM-4 — permissão só na borda

Nenhuma view decide acesso. `@require(...)` em `routes.py`, uma vez por rota.
Hoje há permissão dentro de código de renderização (linha 4458 monta um selo de
professor a partir de checagem de grupo); isso não se reproduz.

---

## 4. Contrato de módulo

Cada módulo tem exatamente quatro arquivos:

| Arquivo | Pode | Não pode |
|---|---|---|
| `__init__.py` | declarar nav, permissão e rotas | conter lógica |
| `routes.py` | orquestrar, exigir permissão | montar HTML, consultar banco |
| `views.py` | montar HTML via `ui/` | consultar banco, decidir permissão |
| `service.py` | regra de negócio, dados | gerar HTML |

Regra de dependência: `modules/ → ui/ → design/` e `modules/ → core/`. Um módulo
nunca importa outro módulo.

---

## 5. Critérios de aceite por módulo

Um módulo só é considerado pronto quando **todos** os itens abaixo passam:

- **A1** — Todas as rotas do módulo respondem no mesmo endereço e método da v1.
- **A2** — Para cada rota × grupo, a decisão de acesso é idêntica à tabela do
  R-PERM-1.
- **A3** — CSRF exigido em todas as rotas de `/action/` (a v1 tem 92 referências;
  nenhuma pode se perder).
- **A4** — Resposta das APIs com as mesmas chaves de topo da v1. Campos novos
  são permitidos; remoção ou renomeação, não.
- **A5** — `service.py` coberto por teste de unidade.
- **A6** — Comparação visual lado a lado com a v1 registrada por quem revisa.
- **A7** — Nenhum segredo em resposta. O smoke test já verifica
  `secrets_exposed: false` em 20 checagens; a v2 mantém.
- **A8** — Remover a linha `register(...)` devolve as rotas ao legado sem
  redeploy.

---

## 6. Pendência de escopo: o módulo `data`

O `data` (Bancos de dados e Tenants) aparece na navegação proposta, mas **não há
rota `/api/` ou `/action/` correspondente na v1** — a gestão de bancos e tenants
hoje é servida dentro de `/cloudiff/portal` por parâmetro de aba
(`?tab=bancos`), sem endpoint próprio.

Decidir antes de implementar:

- **(a)** criar rotas próprias `/cloudiff/portal/dados/...`, quebrando o
  invariante da §1 e exigindo redirecionamento das antigas; ou
- **(b)** manter o roteamento por aba e o `data` como submódulo de `overview`.

A **(b)** preserva o invariante e é a recomendação. A **(a)** é mais limpa e
pode ser feita depois, com os módulos já isolados.

---

## 7. Portões de qualidade

Além do que `scripts/validate.sh` já verifica, passam a reprovar:

| Portão | Limite | Pega |
|---|---|---|
| Testes de `srv/cloudif/tests/` | devem executar | Item 11 do plano |
| `!important` no legado | teto 57 | Regressão de CSS |
| `!important` em `components.css` | 0 | — |
| Literal de cor fora de `tokens.css` | 0 | — |
| Contraste texto/fundo | ≥ 4,5:1 (WCAG AA) | eMAG / LBI |
| Símbolo redefinido no mesmo arquivo | 0 | `profile_mount` duplicado |
| Bloco CSS duplicado | 0 | `.acl-result-*`, `footer.cm-footer` |
| Import entre módulos irmãos | 0 | Erosão da fronteira |
| Rota sem `permission` declarada | 0 | R-PERM-4 |
| Divergência `lib/` × `staging/lib/` | declarada em manifesto | Item 16 |

Os limites de legado já estão em `config/portal-quality-baseline.json`.

---

## 8. Ordem de execução

Do mais isolado para o mais acoplado. Cada etapa é entregável e reversível.

| # | Etapa | Depende de | Entregável |
|---|---|---|---|
| 0 | Tabela de permissões (93 linhas) e reconciliação v54×v56 | — | R-PERM-1, R-PERM-2 |
| 1 | Testes existentes rodando no CI + portões da §7 | — | `validate.sh` ampliado |
| 2 | `health` (8 rotas) | 0, 1 | Primeiro módulo real |
| 3 | `admin` (2 rotas) | 2 | Valida o padrão em escopo pequeno |
| 4 | `delivery` (2 rotas) | 2 | — |
| 5 | `environments` (8 rotas) | 2 | Operações de produção |
| 6 | `projects` (7 rotas) | 2, 5 | O mais acoplado |
| 7 | `overview` (1 rota) | todos | Consome os demais |
| 8 | Remoção do `legacy/` | 7 | Só após uma semana sem fallback |

**A etapa 0 vem antes de qualquer código.** Sem a tabela de permissões, a
conversão vira adivinhação: não há como provar que a v2 decide igual à v1.

---

## 9. Definição de pronto do projeto

A v2 substitui a v1 quando, e somente quando:

1. As 31 rotas são servidas pelos módulos.
2. As 93 combinações rota × grupo conferem com a tabela do R-PERM-1.
3. `registry.match()` não devolve `None` para nenhuma rota durante uma semana de
   tráfego real.
4. O smoke test do control-plane passa nos 150 testes.
5. `--ink-3` e demais tokens passam em WCAG AA.
6. `portal/legacy/` removido.

Enquanto o item 3 não fechar, o legado permanece. Ele é a rede, não dívida.

---

## 10. O que este documento não autoriza

- Substituir a v1 antes da etapa 8.
- Alterar política de acesso a pretexto de "corrigir" na conversão. Divergência
  em relação à v1 é reprovação (A2); mudança de política é decisão à parte.
- Editar release implantado em `app-releases/`. Correção entra pela origem e
  chega por promoção.

---

## Referências

- `docs/PLANO-DE-APERFEICOAMENTO.md` — diagnóstico e fases
- `docs/GUIA-DE-MIGRACAO.md` — arquitetura da v2 e coexistência
- `docs/portal-v2/portal-v2-prototipo.html` — design system de referência
- `config/portal-quality-baseline.json` — limites do legado
