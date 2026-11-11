"""Minimal, instructional academic overview."""
from __future__ import annotations

import html
from urllib.parse import quote

BASE = "/cloudiff/portal"


def _when(value) -> str:
    text=str(value or "").strip()
    if not text:
        return "—"
    try:
        from datetime import datetime
        return datetime.fromisoformat(text.replace("Z","+00:00")).strftime("%d/%m %H:%M")
    except Exception:
        return text.replace("T"," ")[:16]


def _bar(pct: int) -> str:
    pct = max(0, min(100, int(pct or 0)))
    return f'<div class="ov-bar"><span class="ov-bar-fill" style="width:{pct}%"></span></div>'


def _network_graph(node: dict) -> str:
    rx = max(0.0, float(node.get("network_rx_bps") or 0))
    tx = max(0.0, float(node.get("network_tx_bps") or 0))
    peak = max(rx, tx, 1.0)
    rx_pct = max(3, round(100 * rx / peak)) if rx else 0
    tx_pct = max(3, round(100 * tx / peak)) if tx else 0
    return (
        '<div class="network-panel" aria-label="Tráfego de rede do servidor">'
        '<div class="network-panel-head"><div><span class="network-title">Tráfego de rede</span>'
        '<small>Taxa atual recebida e enviada pelo servidor</small></div>'
        '<span class="network-live">Agora</span></div>'
        '<div class="network-chart">'
        '<div class="network-row"><span class="network-key is-rx">Recebimento</span>'
        f'<div class="network-track" role="img" aria-label="Recebimento {node.get("network_rx_label", "-")}"><span class="network-fill is-rx" style="width:{rx_pct}%"></span></div>'
        f'<b>{node.get("network_rx_label", "-")}</b></div>'
        '<div class="network-row"><span class="network-key is-tx">Envio</span>'
        f'<div class="network-track" role="img" aria-label="Envio {node.get("network_tx_label", "-")}"><span class="network-fill is-tx" style="width:{tx_pct}%"></span></div>'
        f'<b>{node.get("network_tx_label", "-")}</b></div>'
        '</div></div>'
    )


def _capacity_chart(metrics: dict) -> str:
    nodes = [node for node in metrics.get("nodes", []) if (node.get("storage_physical_total") or 0) > 0]
    peak = max((float(node.get("storage_physical_total") or 0) for node in nodes), default=1.0)
    rows = []
    for node in nodes:
        total = float(node.get("storage_physical_total") or 0)
        pct = round(100 * total / peak) if peak else 0
        rows.append(
            f'<div class="metric-line"><span>{html.escape(str(node.get("node") or "-"))}</span><b>{metrics["fmt_storage"](total)}</b></div>'
            + _bar(pct)
        )
    return (
        '<article class="resource-card">'
        '<div class="resource-card-head"><div><p class="resource-kicker">Gráfico</p><h3>Capacidade física por servidor</h3></div></div>'
        '<p class="resource-note">Compara os discos físicos instalados; a maior capacidade ocupa 100% da escala.</p>'
        + "".join(rows) + '</article>'
    )


def _memory_chart(metrics: dict) -> str:
    rows = []
    for node in metrics.get("nodes", []):
        if (node.get("mem_total") or 0) <= 0:
            continue
        rows.append(
            f'<div class="metric-line"><span>{html.escape(str(node.get("node") or "-"))}</span>'
            f'<b>{metrics["fmt"](node.get("mem_used"))} de {metrics["fmt"](node.get("mem_total"))}</b></div>'
            + _bar(node.get("mem_pct") or 0)
        )
    return (
        '<article class="resource-card">'
        '<div class="resource-card-head"><div><p class="resource-kicker">Gráfico</p><h3>Uso de memória por servidor</h3></div></div>'
        '<p class="resource-note">Percentual de memória em uso no momento da última coleta.</p>'
        + "".join(rows) + '</article>'
    )


def _platform_charts(metrics: dict) -> str:
    return '<div class="resource-grid">' + _capacity_chart(metrics) + _memory_chart(metrics) + '</div>'


def _server_card(node: dict, fmt, fmt_storage) -> str:
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
        f'<div class="metric-line"><span>Capacidade física instalada</span><b>{fmt_storage(node.get("storage_physical_total") or node["disk_total"])}</b></div>'
        f'<p class="resource-note">{int(node.get("storage_disk_count") or 0)} disco(s) físico(s) detectado(s).</p>'
        f'<div class="metric-line"><span>Sistema (/)</span><b>{fmt_storage(node["disk_used"])} de {fmt_storage(node["disk_total"])}</b></div>{_bar(node["disk_pct"])}'
        + (f'<p class="resource-note">A capacidade física inclui {fmt_storage(node.get("storage_outside_root"))} além do filesystem raiz; o percentual de uso acima mede somente /.</p>'
           if (node.get("storage_outside_root") or 0) > max(5 * 1000**3, 0.05 * (node.get("storage_physical_total") or 0)) else '')
        + f'{_network_graph(node)}</article>'
    )


def _site_card(site: dict) -> str:
    name = html.escape(site.get("name") or site["project_slug"])
    slug = str(site["project_slug"])
    host = html.escape(site.get("stable_hostname") or "")
    manage = f"{BASE}/?tab=publicacao&project={quote(slug, safe='')}"
    if site.get("published") and host:
        badge = '<span class="chip">Publicado</span>'
        address = f'<p class="resource-address">{host}</p>'
        open_action = f'<a class="btn" href="https://{host}" target="_blank" rel="noopener">Abrir site</a>'
    else:
        badge = '<span class="chip is-drift">Ainda não publicado</span>'
        address = '<p class="resource-address">Este projeto ainda não possui endereço público.</p>'
        open_action = ''
    return (
        '<article class="resource-card">'
        f'<div class="resource-card-head"><div><p class="resource-kicker">Site do projeto</p><h3>{name}</h3></div>{badge}</div>'
        f'{address}<div class="resource-actions">{open_action}<a class="btn btn-quiet" href="{manage}">Gerenciar</a></div>'
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


def sites_body(data: dict) -> str:
    resources = data["resources"]
    sites = "".join(_site_card(site) for site in resources["sites"]) or _empty(
        "Você ainda não publicou um site",
        "Publique um projeto quando ele estiver pronto para ser acessado pela comunidade acadêmica.",
        "Ver meus projetos", f"{BASE}/?tab=projetos"
    )
    others = ""
    if resources.get("can_view_others"):
        others = (
            '<div class="other-resources">'
            f'<a href="{BASE}/?tab=publicacao&amp;scope=others#other-user-sites" class="other-link"><span>Sites de outros usuários</span><b>{int(resources.get("other_sites") or 0)}</b></a>'
            '</div>'
        )
    return (
        '<section class="resource-section" aria-labelledby="my-sites-title"><div class="resource-section-head"><div><p class="ov-eyebrow">Publicações</p><h2 id="my-sites-title">Meus sites</h2><p>Todos os seus projetos web, publicados ou em preparação.</p></div>'
        f'</div><div class="resource-grid sites-grid">{sites}</div>{others}</section>'
    )


def _academic_tracking_card(item: dict) -> str:
    if not item.get("ok"):
        return (
            '<article class="resource-card academic-project-card">'
            f'<div class="resource-card-head"><div><p class="resource-kicker">Projeto</p><h3>{html.escape(str(item.get("name") or item.get("slug") or "Projeto"))}</h3></div><span class="chip is-drift">Dados parciais</span></div>'
            '<p class="resource-note">O acompanhamento deste projeto não respondeu agora. O projeto continua disponível no Taiga.</p>'
            f'<a class="btn btn-quiet" href="{BASE}/?tab=taiga&amp;project={quote(str(item.get("slug") or ""),safe="")}">Abrir no Taiga</a></article>'
        )
    channels=item.get("channels_14d") or {}
    production=item.get("production") or {}
    public_requests=production.get("public_requests")
    public_visitors=production.get("public_unique_visitors")
    production_html=(
        '<div class="academic-production">'
        f'<div><span>Produção pública · {int(production.get("window_days") or 7)}d</span><b>{html.escape(str(public_requests if public_requests is not None else "—"))}</b><small>requisições externas</small></div>'
        f'<div><span>Visitantes externos · aprox.</span><b>{html.escape(str(public_visitors if public_visitors is not None else "—"))}</b><small>máximo por host</small></div>'
        f'<div><span>Último acesso público</span><b>{html.escape(_when(production.get("last_seen")))}</b><small>{html.escape(str(production.get("primary_host") or ""))}</small></div>'
        '</div>'
    ) if production.get("published") else '<p class="resource-note">Produção pública ainda não mapeada para este projeto.</p>'
    return (
        '<article class="resource-card academic-project-card">'
        f'<div class="resource-card-head"><div><p class="resource-kicker">Acompanhamento</p><h3>{html.escape(str(item.get("name") or item.get("slug") or "Projeto"))}</h3><small>{html.escape(str(item.get("slug") or ""))}</small></div><span class="chip">{int(item.get("events_14d") or 0)} eventos · 14d</span></div>'
        '<div class="academic-project-metrics">'
        f'<div><span>Membros</span><b>{int(item.get("members") or 0)}</b></div>'
        f'<div><span>Ativos · 7d</span><b>{int(item.get("active_7d") or 0)}</b></div>'
        f'<div><span>Sem atividade registrada · 7d</span><b>{int(item.get("without_activity_7d") or 0)}</b></div>'
        f'<div><span>Tarefas abertas</span><b>{int(item.get("tasks_open") or 0)}</b></div>'
        f'<div><span>Histórias abertas</span><b>{int(item.get("stories_open") or 0)}</b></div>'
        f'<div><span>Última atividade</span><b>{html.escape(_when(item.get("last_activity")))}</b></div>'
        '</div>'
        '<div class="academic-channel-grid">'
        f'<span>Taiga <b>{int(channels.get("taiga") or 0)}</b></span>'
        f'<span>Forgejo <b>{int(channels.get("forgejo") or 0)}</b></span>'
        f'<span>CloudIFF/MCP <b>{int(channels.get("mcp") or 0)}</b></span>'
        f'<span>Ambiente CloudIFF <b>{int(channels.get("environment") or 0)}</b></span>'
        '</div>'+production_html+
        f'<a class="btn btn-quiet" href="{BASE}/?tab=taiga&amp;project={quote(str(item.get("slug") or ""),safe="")}">Ver acompanhamento no Taiga</a>'
        '</article>'
    )


def academic_tracking_body(data: dict) -> str:
    tracking=data.get("academic_tracking") or {}
    if not tracking.get("enabled"):
        return ""
    projects=tracking.get("projects") or []
    cards="".join(_academic_tracking_card(item) for item in projects)
    if not cards:
        cards='<div class="resource-empty"><h3>Nenhum projeto para acompanhar</h3><p>Os projetos autorizados aparecerão aqui quando estiverem disponíveis.</p></div>'
    return (
        '<section class="resource-section academic-tracking" aria-labelledby="academic-tracking-title">'
        '<div class="resource-section-head"><div><p class="ov-eyebrow">Acompanhamento acadêmico</p><h2 id="academic-tracking-title">Sinais dos projetos</h2><p>Resumo factual das fontes instrumentadas para orientar o acompanhamento. O detalhamento permanece no Taiga.</p></div>'
        f'<a href="{BASE}/?tab=taiga">Abrir Taiga</a></div>'
        '<div class="academic-summary-strip">'
        f'<div><span>Projetos</span><b>{int(tracking.get("project_count") or 0)}</b></div>'
        f'<div><span>Membros</span><b>{int(tracking.get("members") or 0)}</b></div>'
        f'<div><span>Ativos · 7d</span><b>{int(tracking.get("active_7d") or 0)}</b></div>'
        f'<div><span>Sem atividade registrada · 7d</span><b>{int(tracking.get("without_activity_7d") or 0)}</b></div>'
        f'<div><span>Eventos · 14d</span><b>{int(tracking.get("events_14d") or 0)}</b></div>'
        f'<div><span>Req. produção · 7d</span><b>{int(tracking.get("production_requests_7d") or 0)}</b></div>'
        '</div>'
        f'<div class="resource-grid academic-project-grid">{cards}</div>'
        '<p class="resource-note academic-tracking-note"><b>Interpretação:</b> “sem atividade registrada” significa ausência de eventos nas fontes atualmente instrumentadas; não é nota, ranking ou prova de que o aluno não trabalhou. Taiga, Forgejo, CloudIFF/MCP e acesso autenticado ao ambiente do projeto estão consolidados. A produção pública é mostrada apenas de forma agregada/anônima; ela não possui identidade institucional confiável e não é atribuída a aluno.</p>'
        '</section>'
    )


def databases_body(data: dict) -> str:
    resources = data.get("resources") or {}
    databases = "".join(_database_card(item) for item in resources.get("databases", [])) or _empty(
        "Nenhum banco vinculado", "Crie ou vincule um banco de dados a um dos seus projetos.",
        "Ir para bancos", f"{BASE}/?tab=bancos"
    )
    others = ""
    if resources.get("can_view_others"):
        others = (
            '<div class="other-resources">'
            f'<a href="{BASE}/?tab=bancos" class="other-link"><span>Bancos de outros usuários</span><b>{int(resources.get("other_databases") or 0)}</b></a>'
            '</div>'
        )
    return (
        '<section class="resource-section overview-loaded-section" aria-labelledby="my-databases-title">'
        '<div class="resource-section-head"><div><p class="ov-eyebrow">Dados</p><h2 id="my-databases-title">Meus bancos</h2><p>Ambientes de dados que você pode usar nos seus projetos.</p></div>'
        f'<a href="{BASE}/?tab=bancos">Gerenciar todos os bancos</a></div><div class="resource-grid">{databases}</div>{others}</section>'
    )


def platform_body(data: dict) -> str:
    metrics = data.get("metrics") or {}
    metrics.setdefault("nodes", [])
    metrics.setdefault("online_count", 0)
    metrics.setdefault("node_count", 0)
    metrics.setdefault("fmt", lambda _value: "-")
    metrics.setdefault("fmt_storage", lambda _value: "-")
    metrics.setdefault("fmt_rate", lambda _value: "-")
    for node in metrics["nodes"]:
        node["network_rx_label"] = metrics["fmt_rate"](node.get("network_rx_bps"))
        node["network_tx_label"] = metrics["fmt_rate"](node.get("network_tx_bps"))
    servers = "".join(_server_card(node, metrics["fmt"], metrics["fmt_storage"]) for node in metrics["nodes"]) or _empty(
        "Métricas indisponíveis", "A coleta da plataforma ainda não enviou dados.", "Ver saúde", f"{BASE}/?tab=monitor-saude"
    )
    return (
        '<section class="resource-section platform-health overview-loaded-section" aria-labelledby="platform-title">'
        '<div class="resource-section-head"><div><p class="ov-eyebrow">Infraestrutura</p><h2 id="platform-title">Saúde da plataforma</h2>'
        f'<p>{int(metrics["online_count"])} de {int(metrics["node_count"])} servidores com coleta recente.</p></div><a href="{BASE}/?tab=monitor-saude">Abrir monitoramento</a></div>'
        f'{_platform_charts(metrics)}<div class="resource-grid server-grid">{servers}</div></section>'
    )


def _master_detail(category: str, data: dict, title: str, description: str, empty_title: str, empty_text: str) -> str:
    items = data.get("items") or []
    rows = []
    for item in items:
        item_id = html.escape(str(item.get("id") or ""), quote=True)
        item_title = html.escape(str(item.get("title") or item_id))
        item_meta = html.escape(str(item.get("meta") or ""))
        rows.append(
            f'<button type="button" class="overview-master-item" data-overview-item="{item_id}" aria-current="false">'
            f'<span class="overview-master-item-title">{item_title}</span><small>{item_meta}</small><span class="overview-master-item-arrow" aria-hidden="true">›</span></button>'
        )
    listing = "".join(rows) or f'<div class="overview-master-empty"><b>{html.escape(empty_title)}</b><p>{html.escape(empty_text)}</p></div>'
    extra = ""
    if category == "resources" and data.get("can_view_others"):
        parts=[]
        if int(data.get("other_sites") or 0):
            parts.append(f'<a class="overview-master-secondary" href="{BASE}/?tab=publicacao&amp;scope=others#other-user-sites">Outros sites <b>{int(data.get("other_sites") or 0)}</b></a>')
        if int(data.get("other_databases") or 0):
            parts.append(f'<a class="overview-master-secondary" href="{BASE}/?tab=bancos">Outros bancos <b>{int(data.get("other_databases") or 0)}</b></a>')
        extra="".join(parts)
    elif category == "publications" and data.get("can_view_others"):
        extra = f'<a class="overview-master-secondary" href="{BASE}/?tab=publicacao&amp;scope=others#other-user-sites">Sites de outros usuários <b>{int(data.get("other_sites") or 0)}</b></a>'
    elif category == "data" and data.get("can_view_others"):
        extra = f'<a class="overview-master-secondary" href="{BASE}/?tab=bancos">Bancos de outros usuários <b>{int(data.get("other_databases") or 0)}</b></a>'
    return (
        '<section class="overview-master" data-overview-master-detail>'
        f'<div class="overview-master-head"><div><p class="ov-eyebrow">Detalhes sob demanda</p><h3>{html.escape(title)}</h3><p>{html.escape(description)}</p></div></div>'
        '<div class="overview-master-layout">'
        f'<nav class="overview-master-list" aria-label="{html.escape(title, quote=True)}">{listing}{extra}</nav>'
        '<div class="overview-master-panel" data-overview-detail aria-live="polite">'
        '<div class="overview-master-placeholder"><p class="ov-eyebrow">Detalhe</p><h3>Selecione um item</h3><p>Somente o item escolhido será carregado e mostrado aqui.</p></div>'
        '</div></div></section>'
    )


def overview_category_body(category: str, data: dict) -> str:
    category = str(category or "").strip().lower()
    if category == "academic":
        return _master_detail(category, data, "Projetos", "Selecione um projeto para consultar o acompanhamento sem carregar todos de uma vez.", "Nenhum projeto", "Não há projetos visíveis para esta sessão.")
    if category == "resources":
        return _master_detail(category, data, "Recursos", "Sites publicados e bancos vinculados aos seus projetos.", "Nenhum recurso", "Sites e bancos vinculados aparecerão aqui.")
    if category == "publications":
        return _master_detail(category, data, "Sites", "Selecione um site para ver endereço, estado e ações de publicação.", "Nenhum site", "Seus projetos publicados ou em preparação aparecerão aqui.")
    if category == "data":
        return _master_detail(category, data, "Bancos e tenants", "Selecione um banco para ver seus vínculos e ações.", "Nenhum banco", "Nenhum tenant de dados está vinculado à sua sessão.")
    if category == "platform":
        return _master_detail(category, data, "Infraestrutura", "Selecione o resumo ou um servidor para consultar apenas aquele detalhe.", "Sem métricas", "Nenhum servidor possui métrica disponível agora.")
    raise ValueError("invalid_overview_category")


def overview_item_body(category: str, data: dict) -> str:
    category = str(category or "").strip().lower()
    if category == "academic":
        project = data.get("project") or {}
        tracking = data.get("tracking")
        if tracking is not None:
            return _academic_tracking_card(tracking)
        slug = str(project.get("slug") or "")
        name = html.escape(str(project.get("name") or slug or "Projeto"))
        status = html.escape(str(project.get("status") or "ativo"))
        return (
            '<article class="resource-card overview-master-detail-card"><div class="resource-card-head"><div>'
            f'<p class="resource-kicker">Projeto</p><h3>{name}</h3><small>{html.escape(slug)}</small></div><span class="chip">{status}</span></div>'
            '<p class="resource-note">Abra o projeto ou o Taiga para consultar tarefas e equipe.</p>'
            f'<div class="resource-actions"><a class="btn" href="{BASE}/?tab=projetos&amp;project={quote(slug,safe="")}">Abrir projeto</a><a class="btn btn-quiet" href="{BASE}/?tab=taiga&amp;project={quote(slug,safe="")}">Abrir no Taiga</a></div></article>'
        )
    if category == "resources":
        if data.get("resource_kind")=="site":
            site=data.get("site")
            if not site: raise ValueError("invalid_overview_item")
            return _site_card(site)
        if data.get("resource_kind")=="database":
            database=data.get("database")
            if not database: raise ValueError("invalid_overview_item")
            return _database_card(database)
        raise ValueError("invalid_overview_item")
    if category == "publications":
        site = data.get("site")
        if not site: raise ValueError("invalid_overview_item")
        return _site_card(site)
    if category == "data":
        database = data.get("database")
        if not database: raise ValueError("invalid_overview_item")
        return _database_card(database)
    if category == "platform":
        if data.get("summary") is not None:
            metrics = data["summary"]
            return (
                '<section class="overview-master-summary"><div class="resource-section-head"><div><p class="ov-eyebrow">Infraestrutura</p><h3>Resumo da plataforma</h3>'
                f'<p>{int(metrics.get("online_count") or 0)} de {int(metrics.get("node_count") or 0)} servidores com coleta recente.</p></div></div>{_platform_charts(metrics)}</section>'
            )
        node = data.get("node")
        if not node: raise ValueError("invalid_overview_item")
        return _server_card(node, data["fmt"], data["fmt_storage"])
    raise ValueError("invalid_overview_category")


def _category_card(key: str, eyebrow: str, title: str, description: str, links: tuple[tuple[str, str], ...], *, lazy: bool = True) -> str:
    links_html = "".join(
        f'<a href="{html.escape(href, quote=True)}">{html.escape(label)}</a>' for label, href in links
    )
    lazy_attrs = f' data-overview-category="{key}"' if lazy else ' data-overview-static="1"'
    status = '<span class="overview-category-status">Abrir para carregar</span>' if lazy else '<span class="overview-category-status">Atalhos</span>'
    body = (
        '<div class="overview-category-content" data-overview-category-body>'
        '<div class="overview-category-placeholder"><p>Os detalhes desta categoria serão carregados somente quando você abrir esta seção.</p></div></div>'
        if lazy else f'<div class="overview-category-content"><div class="overview-link-list">{links_html}</div></div>'
    )
    footer_links = f'<div class="overview-category-links">{links_html}</div>' if lazy and links_html else ''
    return (
        f'<details class="overview-category"{lazy_attrs}><summary><div><p class="ov-eyebrow">{html.escape(eyebrow)}</p>'
        f'<h2>{html.escape(title)}</h2><p>{html.escape(description)}</p></div>{status}</summary>{body}{footer_links}</details>'
    )


def overview_body(data: dict) -> str:
    username = html.escape(data.get("username") or "usuário")
    is_global = bool(data.get("is_global"))
    categories = [
        _category_card(
            "academic", "Projetos", "Projetos",
            "Projetos e acompanhamento.",
            (),
        ),
        _category_card(
            "resources", "Recursos", "Recursos",
            "Sites e bancos vinculados aos projetos.",
            (),
        ),
        _category_card(
            "platform", "Plataforma", "Plataforma",
            "Servidores e saúde da CloudIFF.",
            (),
        ),
    ]
    script = r"""<script id="overview-lazy-categories">(()=>{
 const root=document.querySelector('[data-overview-categories]');if(!root)return;
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 async function request(url){const response=await fetch(url,{credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}}),data=await response.json();if(!response.ok||!data.ok)throw new Error(data.error||('HTTP '+response.status));return data;}
 async function loadCategory(section,force=false){
  const category=section.dataset.overviewCategory,body=section.querySelector('[data-overview-category-body]'),status=section.querySelector('.overview-category-status');
  if(!category||!body||(!force&&section.dataset.loaded==='1')||section.dataset.loading==='1')return;
  section.dataset.loading='1';if(status)status.textContent='Carregando…';body.setAttribute('aria-busy','true');body.innerHTML='<div class="overview-category-loading">Carregando a lista desta categoria…</div>';
  try{const data=await request('/cloudiff/portal/api/overview?category='+encodeURIComponent(category));body.innerHTML=String(data.html||'')+'<div class="overview-category-refresh"><button type="button" class="btn btn-quiet" data-overview-refresh>Atualizar lista</button></div>';section.dataset.loaded='1';if(status)status.textContent='Lista carregada';}
  catch(error){body.innerHTML='<div class="resource-empty"><h3>Não foi possível carregar esta categoria</h3><p>'+esc(error.message||error)+'</p><button type="button" class="btn" data-overview-refresh>Tentar novamente</button></div>';if(status)status.textContent='Falha';}
  finally{section.dataset.loading='0';body.removeAttribute('aria-busy');}
 }
 async function loadItem(button){
  const section=button.closest('[data-overview-category]'),category=section?.dataset.overviewCategory,item=button.dataset.overviewItem,panel=section?.querySelector('[data-overview-detail]');if(!section||!category||!item||!panel)return;
  section.querySelectorAll('[data-overview-item]').forEach(row=>{const active=row===button;row.classList.toggle('is-active',active);row.setAttribute('aria-current',active?'true':'false')});
  panel.setAttribute('aria-busy','true');panel.innerHTML='<div class="overview-master-placeholder"><p class="ov-eyebrow">Detalhe</p><h3>Carregando…</h3><p>Consultando somente o item selecionado.</p></div>';
  try{const data=await request('/cloudiff/portal/api/overview?category='+encodeURIComponent(category)+'&item='+encodeURIComponent(item));panel.innerHTML=String(data.html||'');}
  catch(error){panel.innerHTML='<div class="resource-empty"><h3>Não foi possível carregar o detalhe</h3><p>'+esc(error.message||error)+'</p></div>';}
  finally{panel.removeAttribute('aria-busy');}
 }
 root.querySelectorAll('details.overview-category').forEach(section=>section.addEventListener('toggle',()=>{if(!section.open)return;root.querySelectorAll('details.overview-category').forEach(other=>{if(other!==section)other.open=false});loadCategory(section)}));
 root.addEventListener('click',event=>{const item=event.target.closest('[data-overview-item]');if(item){loadItem(item);return}const button=event.target.closest('[data-overview-refresh]');if(!button)return;const section=button.closest('[data-overview-category]');if(section)loadCategory(section,true)});
})();</script>"""
    return (
        '<section class="welcome-panel overview-welcome"><div><p class="ov-eyebrow">Visão geral</p>'
        f'<h2>Olá, {username}.</h2><p>Escolha uma área para começar.</p></div></section>'
        '<section class="overview-category-shell" aria-labelledby="overview-categories-title"><div class="overview-category-shell-head">'
        '<div><h2 id="overview-categories-title">Áreas</h2><p>Abra somente o que precisa.</p></div></div>'
        f'<div class="overview-category-grid" data-overview-categories>{"".join(categories)}</div></section>{script}'
    )
