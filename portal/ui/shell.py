"""Canonical CloudIFF Portal v2 shell.

Every visible page uses this layout. The navigation is organized into stable
functional areas so legacy and migrated screens expose the same menu.
"""
from __future__ import annotations

from collections import OrderedDict
from html import escape

from portal.core.auth import Identity
from portal.core.rbac import is_admin, is_global
from portal.ui.icons import icon

_FOOTER = (
    "IFFluminense — Campus Bom Jesus do Itabapoana · "
    "Av. Dário Viêira Borges, 235 - Lia Márcia, "
    "Bom Jesus do Itabapoana - RJ, 28360-000 · (22) 3833-9850"
)

_TAB_GROUPS: "OrderedDict[str, tuple[tuple[str, str], ...]]" = OrderedDict(
    (
        (
            "Painel geral",
            (
                ("resumo", "Visão geral"),
                ("publicacao", "Publicações"),
                ("projetos", "Projetos"),
                ("bancos", "Bancos e tenants"),
                ("backup", "Backup"),
                ("agentes", "Conectores"),
            ),
        ),
        (
            "Administração",
            (
                ("admin", "Administração do AD"),
                ("admin-manutencao", "Serviços globais"),
                ("admin-excluir-projeto", "Excluir projeto"),
            ),
        ),
        (
            "Ajuda",
            (("ajuda", "Guia da plataforma"),),
        ),
    )
)

_PROJECT_NAV: "OrderedDict[str, tuple[tuple[str, str], ...]]" = OrderedDict(
    (
        ("Construir", (("git", "Código"), ("capacidades", "Capacidades"))),
        (
            "Entregar",
            (
                ("aprovacoes", "Aprovações"),
                ("publicacao", "Publicação"),
                ("monitor-promocoes", "Histórico"),
            ),
        ),
        (
            "Operar",
            (
                ("operacao-producao", "Produção"),
                ("monitor-transacoes", "Atividades"),
                ("monitor-filas", "Filas"),
                ("monitor-telemetria", "Métricas"),
                ("reconciliacao", "Reconciliação"),
            ),
        ),
    )
)

_PROJECT_TABS = {tab for entries in _PROJECT_NAV.values() for tab, _label in entries}
_PROJECT_DESCRIPTIONS = {
    "git": "Repositórios Forge, integrações e infraestrutura vinculada aos projetos.",
    "capacidades": "Frameworks, capacidades detectadas e ferramentas disponíveis por projeto.",
    "aprovacoes": "Decisões humanas e autorizações pendentes para ações dos projetos.",
    "publicacao": "Versões publicadas, endereço ativo e ativação do site.",
    "monitor-promocoes": "Histórico de promoções, ativações e reversões dos projetos.",
    "operacao-producao": "Operações controladas de produção vinculadas aos projetos autorizados.",
    "monitor-transacoes": "Atividades e transações recentes executadas pelos projetos.",
    "monitor-filas": "Processamento assíncrono, filas e tentativas relacionadas aos projetos.",
    "monitor-telemetria": "Métricas e sinais operacionais consolidados por projeto.",
    "reconciliacao": "Estado desejado, tarefas e reconciliação assíncrona dos projetos.",
}

_TAB_TITLES = {tab: label for entries in _TAB_GROUPS.values() for tab, label in entries}
_TAB_TITLES.update({tab: label for entries in _PROJECT_NAV.values() for tab, label in entries})
_TAB_TITLES["projetos"] = "Projetos"
_ASSET_VERSION = "20260805-1455"

_MODULE_TO_TAB = {
    "overview": "resumo",
    "projects": "projetos",
    "data": "bancos",
    "delivery": "publicacao",
    "environments": "operacao-producao",
    "health": "resumo",
    "admin": "admin",
}


def _primary_group(identity: Identity) -> tuple[str, str]:
    normalized = {group.strip().lower(): group.strip() for group in identity.groups}
    if "cloudif-tenants-admin" in normalized:
        return "Administrador", normalized["cloudif-tenants-admin"]
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
    for section, configured_entries in _TAB_GROUPS.items():
        if section == "Administração" and not is_global(identity):
            continue
        entries = configured_entries
        if section == "Administração" and not is_admin(identity):
            entries = tuple((tab, label) for tab, label in entries if tab in {"admin-manutencao", "admin-excluir-projeto"})
        if allowed_tabs is not None:
            entries = tuple((tab, label) for tab, label in entries if tab in allowed_tabs)
            if not entries:
                continue
        active_group = any(tab == active_tab for tab, _label in entries)
        links = []
        for tab, label in entries:
            current = ' aria-current="page"' if tab == active_tab else ""
            links.append(
                f'<a class="nav-link" href="/cloudiff/portal/?tab={escape(tab)}"{current}>'
                f'{escape(label)}</a>'
            )
        output.append(
            f'<details class="nav-group"{" open" if active_group else ""}>'
            f'<summary class="nav-group-label">{escape(section)}</summary>'
            f'<div class="nav-group-links">{"".join(links)}</div></details>'
        )
    return "".join(output)


def _project_navigation(active_tab: str) -> str:
    groups = []
    for section, entries in _PROJECT_NAV.items():
        links = []
        for tab, label in entries:
            current = ' aria-current="page"' if tab == active_tab else ""
            links.append(f'<a href="/cloudiff/portal/?tab={escape(tab)}"{current}>{escape(label)}</a>')
        groups.append(
            f'<div class="project-context-group"><span>{escape(section)}</span>'
            f'<div>{"".join(links)}</div></div>'
        )
    return '<nav class="project-context-nav" aria-label="Navegação do projeto">' + "".join(groups) + "</nav>"


def _document(
    identity: Identity,
    active_tab: str,
    title: str,
    body: str,
    *,
    extra_head: str = "",
    tail: str = "",
    allowed_modules: set[str] | None = None,
) -> str:
    initials = escape((identity.username[:2] or "u").upper())
    friendly_group, canonical_group = _primary_group(identity)
    group = escape(friendly_group)
    group_id = escape(canonical_group)
    contextual = active_tab in _PROJECT_TABS
    body_class = f'tab-{escape(active_tab)}' + (' project-context-route' if contextual else '')
    description = (
        f'<p class="page-description">{escape(_PROJECT_DESCRIPTIONS.get(active_tab, ""))}</p>'
        if contextual
        else ""
    )
    project_nav = _project_navigation(active_tab) if contextual and active_tab != "publicacao" else ""
    return (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta name="cloudif-release" content="{_ASSET_VERSION}">'
        f'<title>{escape(title)} · CloudIFF</title>'
        '<script>(function(){try{var v=localStorage.getItem("cloudif-theme")||"system";'
        'var d=v==="system"&&window.matchMedia&&matchMedia("(prefers-color-scheme: dark)").matches?"dark":v==="system"?"light":v;'
        'document.documentElement.dataset.theme=d;document.documentElement.dataset.themeChoice=v}catch(e){}}());</script>'
        f'{extra_head}'
        f'<link rel="stylesheet" href="/cloudiff/portal/assets/tokens.css?v={_ASSET_VERSION}">'
        f'<link rel="stylesheet" href="/cloudiff/portal/assets/base.css?v={_ASSET_VERSION}">'
        f'<link rel="stylesheet" href="/cloudiff/portal/assets/components.css?v={_ASSET_VERSION}">'
        f'<script src="/cloudiff/portal/assets/app.js?v={_ASSET_VERSION}" defer></script>'
        f'</head><body class="{body_class}"><a class="skip-link" href="#conteudo-principal">Ir para o conteúdo</a><div class="app">'
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
        '<details class="theme-menu"><summary class="theme-toggle" aria-label="Selecionar tema">'
        '<span aria-hidden="true">◐</span><span>Tema</span></summary>'
        '<div class="theme-picker" role="group" aria-label="Tema da aplicação">'
        '<button type="button" data-theme-choice="light">Claro</button>'
        '<button type="button" data-theme-choice="dark">Escuro</button>'
        '<button type="button" data-theme-choice="system">Sistema</button>'
        '</div></details>'
        '<details class="profile-menu"><summary aria-label="Abrir perfil">'
        f'<span class="avatar" data-primary-group="{group_id}">{icon("user-tie") or initials}</span>'
        '</summary><div class="profile-card">'
        f'<p class="profile-role">{group}</p><strong>{escape(identity.username)}</strong>'
        f'<span>{escape(identity.email or "E-mail não informado")}</span>'
        '<a href="/outpost.goauthentik.io/sign_out">Sair da plataforma</a></div></details>'
        '</header>'
        f'<main class="page" id="conteudo-principal"><div class="page-head"><p class="eyebrow">{group}</p>'
        f'<h1 class="page-title">{escape(title)}</h1>{description}</div>'
        f'{project_nav}{body}</main>'
        f'<footer class="page-footer">{escape(_FOOTER)}</footer></div></div>{tail}</body></html>'
    )


def render(identity: Identity, nav_modules: list[str], active: str, title: str, body: str) -> str:
    active_tab = _MODULE_TO_TAB.get(active, active)
    return _document(identity, active_tab, title, body)


def render_legacy(
    identity: Identity,
    active_tab: str,
    title: str,
    body: str,
    legacy_head: str,
    legacy_scripts: str,
) -> str:
    page_title = _TAB_TITLES.get(active_tab, title)
    contextual = " project-context-content" if active_tab in _PROJECT_TABS and active_tab != "publicacao" else ""
    wrapped = f'<section class="legacy-content{contextual}" data-legacy-tab="{escape(active_tab)}">{body}</section>'
    return _document(identity, active_tab, page_title, wrapped, extra_head=legacy_head, tail=legacy_scripts)
