"""Canonical CloudIFF Portal v2 shell.

Every visible GET page uses this layout. Access decisions are made before this
module: it receives an identity and renders only navigation allowed to it.
"""
from __future__ import annotations

from html import escape
from collections import OrderedDict

from portal.core.auth import Identity
from portal.core.rbac import is_global
from portal.ui.icons import icon

_FOOTER = (
    "IFFluminense — Campus Bom Jesus do Itabapoana · "
    "Av. Dário Viêira Borges, 235 - Lia Márcia, "
    "Bom Jesus do Itabapoana - RJ, 28360-000 · (22) 3833-9850"
)

_TAB_GROUPS: "OrderedDict[str, tuple[tuple[str, str], ...]]" = OrderedDict(
    (
        ("Painel", (("resumo", "Visão geral"),)),
        (
            "Projetos",
            (
                ("projetos", "Todos os projetos"),
                ("opcoes-projeto", "Recursos"),
                ("capacidades", "Ferramentas do projeto"),
                ("aprovacoes", "Aprovações"),
                ("publicacao", "Publicação"),
                ("git", "Código e infraestrutura"),
                ("monitor-promocoes", "Histórico"),
                ("operacao-producao", "Produção"),
                ("monitor-transacoes", "Atividades"),
                ("monitor-filas", "Filas"),
                ("monitor-telemetria", "Métricas"),
                ("reconciliacao", "Reconciliação"),
                ("agentes", "Conectar IA"),
                ("gestao-agentes", "Agentes"),
                ("documentacao-mcp", "MCP"),
            ),
        ),
        ("Dados", (("bancos", "Bancos e tenants"),)),
        ("Ferramentas", (("monitor-saude", "Saúde da plataforma"),)),
        ("Administração", (("admin-usuarios", "Usuários"), ("admin-politicas", "Acessos"), ("admin-identidades", "Identidades"), ("admin-configuracoes", "Configurações"), ("admin-auditoria", "Auditoria"), ("admin-manutencao", "Manutenção"))),
        ("Ajuda", (("ajuda", "Primeiros passos"), ("ajuda-token", "Tokens"), ("ajuda-conectar", "Clientes"), ("ajuda-aprovacoes", "Papéis"), ("ajuda-ferramentas", "Referência"))),
    )
)

_TAB_TITLES = {tab: label for entries in _TAB_GROUPS.values() for tab, label in entries}

_MODULE_TO_TAB = {
    "overview": "resumo",
    "projects": "projetos",
    "data": "bancos",
    "delivery": "publicacao",
    "environments": "operacao-producao",
    "health": "monitor-saude",
    "admin": "admin-usuarios",
}


def _primary_group(identity: Identity) -> tuple[str, str]:
    normalized = {group.strip().lower(): group.strip() for group in identity.groups}
    if "cloudif-tenants-admin" in normalized:
        return "Administrador", normalized["cloudif-tenants-admin"]
    if "domain admins" in normalized:
        return "Administrador", normalized["domain admins"]
    if "cloudif-professor" in normalized:
        return "Professor", normalized["cloudif-professor"]
    if "cloudif-aluno" in normalized:
        return "Aluno", normalized["cloudif-aluno"]
    if "cloudif-tenants" in normalized:
        return "Tenant", normalized["cloudif-tenants"]
    return "Tenant", "Usuário"


def _navigation(identity: Identity, active_tab: str, allowed_modules: set[str] | None = None) -> str:
    output: list[str] = []
    allowed_tabs = None if allowed_modules is None else {_MODULE_TO_TAB.get(module, module) for module in allowed_modules}
    for section, entries in _TAB_GROUPS.items():
        if section == "Administração" and not is_global(identity):
            continue
        if allowed_tabs is not None:
            entries = tuple((tab, label) for tab, label in entries if tab in allowed_tabs)
            if not entries:
                continue
        active_group = any(tab == active_tab for tab, _label in entries)
        links = []
        for tab, label in entries:
            current = ' aria-current="page"' if tab == active_tab else ""
            links.append(f'<a class="nav-link" href="/cloudiff/portal/?tab={escape(tab)}"{current}>{escape(label)}</a>')
        output.append(
            f'<details class="nav-group"{" open" if active_group else ""}>'
            f'<summary class="nav-group-label">{escape(section)}</summary>'
            f'<div class="nav-group-links">{"".join(links)}</div></details>'
        )
    return "".join(output)


def _document(identity: Identity, active_tab: str, title: str, body: str, *, extra_head: str = "", tail: str = "", allowed_modules: set[str] | None = None) -> str:
    initials = escape((identity.username[:2] or "u").upper())
    friendly_group, canonical_group = _primary_group(identity)
    group = escape(friendly_group)
    group_id = escape(canonical_group)
    return (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(title)} · CloudIFF</title>{extra_head}"
        '<link rel="stylesheet" href="/cloudiff/portal/assets/tokens.css">'
        '<link rel="stylesheet" href="/cloudiff/portal/assets/base.css">'
        '<link rel="stylesheet" href="/cloudiff/portal/assets/components.css">'
        '<script src="/cloudiff/portal/assets/app.js" defer></script>'
        '</head><body><a class="skip-link" href="#conteudo-principal">Ir para o conteúdo</a><div class="app">'
        '<nav class="nav" id="nav" aria-label="Navegação principal">'
        '<div class="nav-brand"><span class="nav-mark">CI</span>'
        '<span><span class="nav-brand-name">CloudIFF</span>'
        '<span class="nav-brand-sub">Portal acadêmico</span></span></div>'
        f'<div class="nav-scroll">{_navigation(identity, active_tab, allowed_modules)}</div>'
        f'<div class="nav-foot">{escape(_FOOTER)}</div></nav>'
        '<div class="main"><header class="bar">'
        '<button class="bar-toggle" id="toggle" aria-label="Abrir navegação" aria-expanded="false" aria-controls="nav">☰</button>'
        '<span class="scope"><span class="scope-dot"></span>Ambiente acadêmico</span>'
        '<a class="search" href="/cloudiff/portal/?tab=projetos">Buscar em projetos</a>'
        '<details class="profile-menu"><summary aria-label="Abrir perfil">'
        f'<span class="avatar" data-primary-group="{group_id}">{icon("user-tie") or initials}</span>'
        '</summary><div class="profile-card">'
        f'<p class="profile-role">{group}</p><strong>{escape(identity.username)}</strong>'
        f'<span>{escape(identity.email or "E-mail não informado")}</span>'
        '<a href="/outpost.goauthentik.io/sign_out">Sair da plataforma</a></div></details>'
        '</header>'
        f'<main class="page" id="conteudo-principal"><div class="page-head"><p class="eyebrow">{group}</p>'
        f'<h1 class="page-title">{escape(title)}</h1></div>{body}</main>'
        f'<footer class="page-footer">{escape(_FOOTER)}</footer></div></div>{tail}</body></html>'
    )


def render(identity: Identity, nav_modules: list[str], active: str, title: str, body: str) -> str:
    """Render native v2 modules in the same canonical shell."""
    active_tab = _MODULE_TO_TAB.get(active, active)
    return _document(identity, active_tab, title, body, allowed_modules=set(nav_modules))


def render_legacy(identity: Identity, active_tab: str, title: str, body: str, legacy_head: str, legacy_scripts: str) -> str:
    """Render a legacy page body without its old header/navigation."""
    page_title = _TAB_TITLES.get(active_tab, title)
    wrapped = f'<section class="legacy-content" data-legacy-tab="{escape(active_tab)}">{body}</section>'
    return _document(identity, active_tab, page_title, wrapped, extra_head=legacy_head, tail=legacy_scripts)
