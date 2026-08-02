"""Minimal, instructional academic overview."""
from __future__ import annotations

import html

BASE = "/cloudiff/portal"


def _bar(pct: int) -> str:
    pct = max(0, min(100, int(pct or 0)))
    return f'<div class="ov-bar"><span class="ov-bar-fill" style="width:{pct}%"></span></div>'


def _server_card(node: dict, fmt) -> str:
    if node["online"]:
        state, detail = '<span class="chip">Disponível</span>', "Coleta recente"
    elif node["stale"]:
        state, detail = '<span class="chip is-drift">Dados atrasados</span>', "A última coleta está desatualizada"
    else:
        state, detail = '<span class="chip is-halt">Indisponível</span>', "O agente de métricas não respondeu"
    return (
        '<article class="resource-card server-card">'
        f'<div class="resource-card-head"><div><p class="resource-kicker">Servidor</p><h3>{html.escape(node["node"])}</h3></div>{state}</div>'
        f'<p class="resource-note">{detail}</p>'
        f'<div class="metric-line"><span>Memória</span><b>{fmt(node["mem_used"])} de {fmt(node["mem_total"])}</b></div>{_bar(node["mem_pct"])}'
        f'<div class="metric-line"><span>Armazenamento</span><b>{fmt(node["disk_used"])} de {fmt(node["disk_total"])}</b></div>{_bar(node["disk_pct"])}'
        '</article>'
    )


def _site_card(site: dict) -> str:
    name = html.escape(site.get("name") or site["project_slug"])
    host = html.escape(site.get("stable_hostname") or "")
    href = "https://" + host if host else f"{BASE}/?tab=publicacao"
    return (
        '<article class="resource-card">'
        f'<div class="resource-card-head"><div><p class="resource-kicker">Site publicado</p><h3>{name}</h3></div><span class="chip">No ar</span></div>'
        f'<p class="resource-address">{host or "Endereço não informado"}</p>'
        f'<div class="resource-actions"><a class="btn" href="{href}" target="_blank" rel="noopener">Abrir site</a><a class="btn btn-quiet" href="{BASE}/?tab=publicacao">Gerenciar</a></div>'
        '</article>'
    )


def _database_card(database: dict) -> str:
    tenant = html.escape(database["tenant"])
    count = len(database["projects"])
    text = "Disponível para seus projetos" if count == 0 else (f"{count} projeto vinculado" if count == 1 else f"{count} projetos vinculados")
    return (
        '<article class="resource-card">'
        f'<div class="resource-card-head"><div><p class="resource-kicker">Banco acadêmico</p><h3>{tenant}</h3></div><span class="chip">Disponível</span></div>'
        f'<p class="resource-note">{text}</p><a class="btn btn-quiet" href="{BASE}/?tab=bancos">Abrir banco</a>'
        '</article>'
    )


def _empty(title: str, text: str, label: str, href: str) -> str:
    return f'<div class="resource-empty"><h3>{html.escape(title)}</h3><p>{html.escape(text)}</p><a class="btn" href="{href}">{html.escape(label)}</a></div>'


def overview_body(data: dict) -> str:
    metrics, resources = data["metrics"], data["resources"]
    username = html.escape(data["username"] or "usuário")
    sites = "".join(_site_card(site) for site in resources["sites"]) or _empty(
        "Você ainda não publicou um site",
        "Publique um projeto quando ele estiver pronto para ser acessado pela comunidade acadêmica.",
        "Ver meus projetos", f"{BASE}/?tab=projetos"
    )
    databases = "".join(_database_card(item) for item in resources["databases"]) or _empty(
        "Nenhum banco vinculado", "Crie ou vincule um banco de dados a um dos seus projetos.",
        "Ir para bancos", f"{BASE}/?tab=bancos"
    )
    servers = "".join(_server_card(node, metrics["fmt"]) for node in metrics["nodes"]) or _empty(
        "Métricas indisponíveis", "A coleta da plataforma ainda não enviou dados.", "Ver saúde", f"{BASE}/?tab=monitor-saude"
    )
    others = ""
    if resources["can_view_others"]:
        others = (
            '<div class="other-resources">'
            f'<a href="{BASE}/?tab=publicacao" class="other-link"><span>Sites de outros usuários</span><b>{resources["other_sites"]}</b></a>'
            f'<a href="{BASE}/?tab=bancos" class="other-link"><span>Bancos de outros usuários</span><b>{resources["other_databases"]}</b></a>'
            '</div>'
        )
    return (
        '<section class="welcome-panel"><div><p class="ov-eyebrow">Seu espaço acadêmico</p>'
        f'<h2>Olá, {username}.</h2><p>Aqui você encontra o que está publicando, os bancos ligados aos seus projetos e os caminhos mais usados para continuar seu trabalho.</p></div>'
        f'<div class="welcome-actions"><a class="btn" href="{BASE}/?tab=projetos">Continuar um projeto</a><a class="btn btn-quiet" href="{BASE}/?tab=ajuda">Primeiros passos</a></div></section>'
        '<section class="resource-section" aria-labelledby="my-sites-title"><div class="resource-section-head"><div><p class="ov-eyebrow">Publicações</p><h2 id="my-sites-title">Meus sites</h2><p>Sites que estão disponíveis na internet a partir dos seus projetos.</p></div>'
        f'<a href="{BASE}/?tab=publicacao">Ver todas as publicações</a></div><div class="resource-grid">{sites}</div></section>'
        '<section class="resource-section" aria-labelledby="my-databases-title"><div class="resource-section-head"><div><p class="ov-eyebrow">Dados</p><h2 id="my-databases-title">Meus bancos</h2><p>Ambientes de dados que você pode usar nos seus projetos.</p></div>'
        f'<a href="{BASE}/?tab=bancos">Gerenciar todos os bancos</a></div><div class="resource-grid">{databases}</div>{others}</section>'
        '<section class="resource-section platform-health" aria-labelledby="platform-title"><div class="resource-section-head"><div><p class="ov-eyebrow">Plataforma</p><h2 id="platform-title">Saúde da plataforma</h2>'
        f'<p>{metrics["online_count"]} de {metrics["node_count"]} servidores com coleta recente.</p></div><a href="{BASE}/?tab=monitor-saude">Abrir monitoramento</a></div><div class="resource-grid server-grid">{servers}</div></section>'
    )
