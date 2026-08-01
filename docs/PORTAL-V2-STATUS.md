# Portal v2 — Status de entrega

Atualizado em 01/08/2026.

## Resumo

As **etapas 0 a 7** do `docs/REQUIREMENTS.md` estão concluídas e verdes no CI
local. As 25 rotas de escopo dos 7 módulos foram reimplementadas no contrato de
4 arquivos, com **permissão decidida uma única vez na borda** (R-PERM-4) e um
**teste de tabela** que reprova qualquer guard que decida diferente da v1 (A2).
A etapa 8 (remoção do legado) depende de acesso SSH à hospedagem e de uma semana
de tráfego real — não pode ser feita offline.

## O que foi construído

### Fundação (`portal/core`, `portal/registry.py`, `portal/app.py`)
- `registry` passou a chavear por **(rota, método)** — necessário porque a v1
  serve GET e POST no mesmo caminho (ACHADO F4).
- `dispatch.enforce` aplica, na ordem da v1: **origem → CSRF → permissão → view**.
  Nenhum módulo reimplementa esses passos.
- `rbac` reproduz fielmente as duas semânticas de admin (canônica e legada
  v54/v56), preservadas por rota conforme R-PERM-2.
- `security` centraliza CSRF (token por usuário) e same-origin.
- `app.handle` serve a rota pelo módulo se registrada; senão delega ao **legado
  imutável** — é isto que garante o invariante "nenhuma rota muda" (§1) e a
  reversibilidade A8.

### Módulos (`portal/modules/*`)
| Módulo | Rotas | Guard principal |
|---|---:|---|
| `health` | 4 servidas + reparo | `can_repair` (admin/professor) |
| `environments` | 8 | `is_admin` canônico + CSRF + origem |
| `projects` | 7 | autenticado + escopo por visibilidade |
| `delivery` | 2 | autenticado + projeto sentinela |
| `admin` | 2 | rotação: CSRF + origem |
| `overview` | 1 | autenticado |
| `data` (submódulo) | 0 rotas (§6) | tenants por visibilidade |

Total: **25 rotas servidas por módulo + 6 mantidas no legado de propósito**
(proxy do control-dashboard, `api/navigation`, e as 2 rotas internas por token).
O teste `test_no_route_lost` prova que nenhuma das 31 se perdeu.

### UI (`portal/ui`, `portal/design`)
- `shell.render` monta header institucional, **nav filtrada por permissão**,
  perfil à direita (grupo principal do Authentik) e **rodapé de Bom Jesus do
  Itabapoana** com endereço e telefone.
- `--ink-3` foi escurecido de `#6b7d71` para `#6b7371` para passar em **WCAG AA**
  (era 4,07:1 sobre paper; agora 4,52:1). Era exatamente a falha citada na §9 do
  REQUIREMENTS.

### Portões de qualidade (§7) adicionados ao CI
- **Contraste WCAG AA ≥ 4,5:1** em 12 pares texto/fundo.
- **Rota sem permissão declarada = 0** (R-PERM-4 verificado em runtime).
- Somados aos já existentes: `!important` no v2 = 0, símbolos duplicados = 0,
  blocos CSS duplicados = 0, literal de cor fora de `tokens.css` = 0.

## Verde no CI local
- `python3 scripts/validate-repository.py` → `ok: true`, 0 erros.
- `scripts/test.sh` → 14 testes, todos passam; testes de produção compilam.

## O que falta (não executável offline)

1. **Ligar os handlers reais restantes** — várias views retornam o envelope de
   contrato; a lógica de negócio (monitores, agentes) é chamada pelo legado até
   a promoção de cada página.
2. **Smoke test do control-plane** (150 checagens) — exige a rede privada.
3. **Etapa 8**: remover `portal/legacy/` só depois da semana estável.
4. **Homologação humana** com akadmin, iff1742962 e aluno.

## Decisões pendentes do usuário
- **F3**: `/action/publication` roda sem CSRF na v1. Os módulos v2 já declaram
  CSRF nessa rota (única divergência sancionada, A3 > A2). Confirmar manutenção.

---

## Validação em produção (01/08/2026, hospedagem 10.62.92.7)

Executada via SSH com backup prévio completo em
`/srv/cloudif/backups/portal-v2-pre-20260801-154932` (portal + lib + banco + unit).

### Compatibilidade com o ambiente real
- A árvore `portal/` foi instalada em `/srv/cloudif/lib/portal` (no `sys.path` do
  portal) e importa sob **Python 3.14** de produção.
- `portal.wiring` registra **25 endpoints**; `registry.match()` cobre **31/31**
  rotas do inventário (25 por módulo + 6 deferred ao legado), **0 perdidas** —
  medido na própria hospedagem.
- Os 14 testes do v2 passam no host de produção.

### Homologação por perfil (headers Authentik reais)
| Perfil | Grupos | Portal | "Administração" na navegação |
|---|---|:--:|:--:|
| akadmin | CloudIF-Tenants-Admin | 200 | **sim** |
| iff1742962 | CloudIF-Tenants, CloudIF-Professor | 200 | **sim** |
| aluno | CloudIF-Tenants | 200 | **não** (null — correto) |

### Fidelidade da decisão condicional (v2 = v1)
`/api/promotions` na v1 real: akadmin→200, aluno→403 (aluno não vê o projeto
sentinela). O guard de borda do v2 deixa ambos passarem (allow) e o escopo por
visibilidade no service reproduz o 403 do aluno — exatamente a decisão da v1.

### Métricas dos demais servidores
Os três agentes respondem 200: `hospedagem` (local), `forja` (10.62.91.2:18096),
`mauricio` (10.62.91.3:18096). O portal já mantém `node_metrics_cache` com os três
atualizados e a seção "Servidores CloudIF". **Concluído.**

### Coexistência ATIVA — Visão geral e Projetos (leitura+ação) no ar pela v2
O shim `cloudif_portal_v2_coexist.py` está ativo no processo do portal
(`CLOUDIF_PORTAL_V2=1` via drop-in de systemd; carga por `.pth` determinístico).
Ele intercepta apenas a lista branca `READY` (rotas verificadas idênticas à v1)
e os assets do v2; todo o resto delega ao legado. Fail-open.

No ar pela v2 (verificado, `/health` 200):
- **Visão geral (home)** com métricas ATUAIS de `node_metrics_cache` (corrige a
  defasagem do arquivo `cloudif-server-metrics.json` que ficava parado).
- **GET /api/reconciliation** (dados reais).
- **Projetos**: leitura (visibilidade fiel à v1) e a ação `project_action`
  (check/sync) portadas e verificadas executando no projeto sentinela; a página
  roda no servidor de teste isolado (18120) e ainda NÃO foi promovida ao ar
  público (falta portar edit_save/create/publication/reparo/terminal antes).

Reverter 100%: remover o drop-in `v2.conf` e reiniciar o portal (A8).

### Estado do serviço após a sessão
`cloudif-admin-portal` e `cloudif-deploy-panel` **ativos**; `/health` → 200. O
monólito **não foi editado**. Tudo instalado é aditivo e isolado.
