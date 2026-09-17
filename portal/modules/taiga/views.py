"""Professional project-first Taiga telemetry dashboard."""
from __future__ import annotations

import html
from datetime import datetime
from urllib.parse import quote

BASE = "/cloudiff/portal"
TAIGA = "https://taiga.cloudiff.duckdns.org"


def h(value) -> str:
    return html.escape(str(value or ""), quote=True)


def _status(ok: bool, yes: str = "Disponível", no: str = "Atenção") -> str:
    return f'<span class="chip{'' if ok else ' is-drift'}">{h(yes if ok else no)}</span>'


def _when(value) -> str:
    text=str(value or "").strip()
    if not text:return "—"
    try:
        dt=datetime.fromisoformat(text.replace("Z","+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return text.replace("T"," ")[:16]


def _catalog(data: dict) -> str:
    cards=[]
    for project in data.get("projects") or []:
        slug=str(project.get("slug") or "")
        status=str(project.get("status") or "ativo").strip() or "ativo"
        cards.append(
            f'<a class="taiga-project-card" href="{BASE}/?tab=taiga&amp;project={quote(slug,safe="")}">'
            '<div class="taiga-project-card-top">'
            f'<div><p class="resource-kicker">Projeto</p><h3>{h(project.get("name") or slug)}</h3><p class="taiga-project-slug">{h(slug)}</p></div>'
            f'<span class="chip">{h(status)}</span></div>'
            f'<p class="resource-note">{h(project.get("description") or "Projeto autorizado pela ACL CloudIFF.")}</p>'
            '<div class="taiga-project-meta">'
            f'<span><b>Responsável</b>{h(project.get("owner") or "—")}</span>'
            f'<span><b>Atualização</b>{h(_when(project.get("updated_at")))}</span>'
            '</div><span class="taiga-project-open">Abrir painel <b>→</b></span></a>'
        )
    content=''.join(cards) if cards else '<div class="resource-empty"><h3>Nenhum projeto visível</h3><p>O Taiga usa exatamente a mesma visibilidade dos projetos CloudIFF.</p></div>'
    taiga=data.get("taiga") or {};faro=data.get("faro") or {}
    return (
        '<section class="taiga-catalog">'
        '<div class="taiga-catalog-head"><div><p class="ov-eyebrow">Taiga</p><h2>Projetos</h2><p>Escolha um projeto para abrir indicadores, atividade histórica, acessos e acompanhamento acadêmico.</p></div>'
        '<div class="taiga-platform-state">'
        f'<span>Taiga {_status(bool(taiga.get("ok")),"online","atenção")}</span>'
        f'<span>Faro {_status(bool(faro.get("ok")),"online","atenção")}</span>'
        f'<span class="taiga-project-total">{h(data.get("project_count") or 0)} projeto(s)</span></div></div>'
        f'<div class="taiga-project-grid">{content}</div></section>'
    )


def _project_header(data: dict) -> str:
    project=data.get("selected_project") or {}; private=data.get("taiga_project") or {}
    slug=str(project.get("slug") or "")
    if data.get("can_view_members"):
        open_action=(
            f'<form method="post" action="{BASE}/action/taiga-access">'
            f'<input type="hidden" name="csrf_token" value="{h(data.get("csrf") or "")}">'
            f'<input type="hidden" name="project" value="{h(slug)}">'
            '<button class="btn" type="submit">Abrir no Taiga</button></form>'
        )
    else:
        open_action=f'<a class="btn" target="_blank" rel="noopener" href="{h(private.get("url") or TAIGA)}">Abrir no Taiga</a>'
    return (
        '<section class="taiga-detail-head">'
        f'<a class="taiga-back" href="{BASE}/?tab=taiga">← Todos os projetos</a>'
        '<div class="taiga-detail-title"><div>'
        f'<p class="ov-eyebrow">Projeto · {h(slug)}</p><h2>{h(project.get("name") or slug)}</h2>'
        f'<p>{h(project.get("description") or "Acompanhamento consolidado do projeto no CloudIFF e Taiga.")}</p>'
        '</div><div class="resource-actions">'+open_action+'</div></div></section>'
    )


def _kpis(data: dict) -> str:
    item=data.get("taiga_project") or {}; counts=item.get("counts") or {}; dash=data.get("dashboard") or {}
    rows=(("Tarefas",counts.get("tasks"),f'{int(counts.get("tasks_closed") or 0)} concluídas'),
          ("Histórias",counts.get("userstories"),f'{int(counts.get("userstories_closed") or 0)} concluídas'),
          ("Etapas",counts.get("milestones"),f'{int(counts.get("milestones_closed") or 0)} concluídas'),
          ("Membros",counts.get("members"),f'{int(dash.get("active_users") or 0)} com atividade recente'),
          ("Eventos",dash.get("activity_total"),"histórico consolidado"))
    cards=''.join(f'<article class="taiga-kpi"><span>{h(label)}</span><strong>{h(value if value is not None else "—")}</strong><small>{h(note)}</small></article>' for label,value,note in rows)
    return '<div class="taiga-kpi-grid">'+cards+'</div>'


def _completion(data: dict) -> str:
    rows=[]
    for item in (data.get("dashboard") or {}).get("completion") or []:
        pct=max(0,min(100,int(item.get("pct") or 0)))
        rows.append(
            '<div class="taiga-progress-row"><div class="taiga-progress-copy">'
            f'<span>{h(item.get("label"))}</span><b>{h(item.get("closed"))} / {h(item.get("total"))}</b></div>'
            f'<div class="ov-bar"><span class="ov-bar-fill" style="width:{pct}%"></span></div><small>{pct}% concluído · {h(item.get("open"))} em aberto</small></div>'
        )
    return ''.join(rows) or '<p class="resource-note">Ainda não há itens de trabalho contabilizados.</p>'


def _history_chart(data: dict) -> str:
    series=(data.get("dashboard") or {}).get("history") or []
    peak=max((int(x.get("events") or 0) for x in series),default=1)
    bars=[]
    for item in series:
        value=int(item.get("events") or 0);height=0 if value<=0 else max(6,round(100*value/peak))
        bars.append(
            '<div class="taiga-history-item">'
            f'<div class="taiga-history-track" title="{h(item.get("label"))}: {value} evento(s)"><span style="height:{height}%"></span></div>'
            f'<b>{value}</b><small>{h(item.get("label"))}</small></div>'
        )
    return '<div class="taiga-history-chart" role="img" aria-label="Atividade diária recente">'+''.join(bars)+'</div>' if bars else '<p class="resource-note">Sem histórico recente.</p>'


def _source_chart(data: dict) -> str:
    rows=[]
    for item in (data.get("dashboard") or {}).get("sources") or []:
        pct=max(0,min(100,int(item.get("pct") or 0)))
        rows.append(
            '<div class="taiga-source-row"><div><span>'+h(item.get("label"))+'</span><b>'+h(item.get("count"))+'</b></div>'
            f'<div class="ov-bar"><span class="ov-bar-fill" style="width:{pct}%"></span></div></div>'
        )
    return ''.join(rows) or '<p class="resource-note">Nenhuma fonte de atividade registrada.</p>'


def _recent_accesses(data: dict) -> str:
    rows=[]
    for item in (data.get("dashboard") or {}).get("recent_accesses") or []:
        rows.append(
            '<tr>'
            f'<td><strong>{h(item.get("full_name") or item.get("username"))}</strong><br><small>{h(item.get("username"))}</small></td>'
            f'<td>{h(item.get("role") or "—")}</td><td>{h(_when(item.get("last_login")))}</td>'
            f'<td>{h(_when(item.get("last_activity")))}</td><td>{h(item.get("estimated_active_minutes") or 0)} min</td></tr>'
        )
    if not rows:return '<div class="resource-empty taiga-empty-compact"><h3>Sem acessos recentes</h3><p>Os acessos aparecerão aqui quando houver eventos autenticados.</p></div>'
    return '<div class="table-scroll"><table class="cm-table taiga-table"><thead><tr><th>Usuário</th><th>Papel</th><th>Último login</th><th>Última atividade</th><th>Atividade estimada</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'


def _student_history_chart(history: list[dict], shared_peak: int = 0) -> str:
    points=history or []
    peak=max(shared_peak,max((int(item.get("events") or 0) for item in points),default=0),1)
    bars=[]
    for item in points:
        value=int(item.get("events") or 0)
        height=0 if value<=0 else max(8,round(100*value/peak))
        bars.append(
            '<span class="taiga-student-bar" '
            f'style="height:{height}%" title="{h(item.get("label"))}: {value} evento(s)"></span>'
        )
    return '<div class="taiga-student-spark" role="img" aria-label="Atividade do aluno nos últimos 14 dias">'+''.join(bars)+'</div>'


def _student_card(actor: dict, shared_peak: int) -> str:
    total=int(actor.get("total") or 0)
    tasks_closed=int(actor.get("tasks_closed") or 0);tasks_total=int(actor.get("tasks_assigned") or 0)
    stories_closed=int(actor.get("stories_closed") or 0);stories_total=int(actor.get("stories_assigned") or 0)
    minutes=int(actor.get("estimated_active_minutes") or 0)
    return (
        '<article class="taiga-student-card">'
        '<div class="taiga-student-head"><div>'
        f'<h3>{h(actor.get("full_name") or actor.get("username"))}</h3><p>{h(actor.get("username"))}</p>'
        f'</div><span class="chip">{h(actor.get("role") or "membro")}</span></div>'
        '<div class="taiga-student-metrics">'
        f'<div><span>Tarefas</span><b>{tasks_closed}/{tasks_total}</b></div>'
        f'<div><span>Histórias</span><b>{stories_closed}/{stories_total}</b></div>'
        f'<div><span>Eventos</span><b>{total}</b></div>'
        f'<div><span>Atividade</span><b>{minutes} min</b></div></div>'
        '<div class="taiga-student-chart-head"><span>Atividade · 14 dias</span>'
        f'<small>Última: {h(_when(actor.get("last_activity")))}</small></div>'
        +_student_history_chart(actor.get("history") or [],shared_peak)+
        '</article>'
    )


def _members(data: dict) -> str:
    if not data.get("can_view_members"):
        subject=data.get("subject") or {}
        history=subject.get("history") or []
        peak=max((int(item.get("events") or 0) for item in history),default=1)
        return (
            '<div class="taiga-student-self">'
            '<div class="taiga-personal-grid">'
            f'<div><span>Tarefas</span><b>{h(subject.get("tasks_closed") or 0)} / {h(subject.get("tasks_assigned") or 0)}</b></div>'
            f'<div><span>Histórias</span><b>{h(subject.get("stories_closed") or 0)} / {h(subject.get("stories_assigned") or 0)}</b></div>'
            f'<div><span>Atividade estimada</span><b>{h(subject.get("estimated_active_minutes") or 0)} min</b></div>'
            f'<div><span>Último login</span><b>{h(_when(subject.get("last_login")))}</b></div></div>'
            '<div class="resource-card taiga-student-self-chart"><div class="taiga-panel-head"><div><p class="resource-kicker">Meu histórico</p><h3>Atividade nos últimos 14 dias</h3></div></div>'
            +_student_history_chart(history,peak)+'</div></div>'
        )
    actors=data.get("actors") or []
    if not actors:
        return '<p class="resource-note">Ainda não há atividade individual normalizada para os membros.</p>'
    shared_peak=max((int(point.get("events") or 0) for actor in actors for point in (actor.get("history") or [])),default=1)
    cards=''.join(_student_card(actor,shared_peak) for actor in actors)
    rows=[]
    for a in actors:
        rows.append(
            '<tr>'
            f'<td><strong>{h(a.get("full_name") or a.get("username"))}</strong><br><small>{h(a.get("username"))}</small></td>'
            f'<td>{h(a.get("role") or "—")}</td><td>{h(a.get("tasks_closed") or 0)}/{h(a.get("tasks_assigned") or 0)}</td>'
            f'<td>{h(a.get("stories_closed") or 0)}/{h(a.get("stories_assigned") or 0)}</td><td>{h(a.get("total") or 0)}</td>'
            f'<td>{h(a.get("estimated_active_minutes") or 0)} min</td><td>{h(_when(a.get("last_activity")))}</td></tr>'
        )
    table='<div class="table-scroll taiga-student-table"><table class="cm-table taiga-table"><thead><tr><th>Aluno</th><th>Papel</th><th>Tarefas</th><th>Histórias</th><th>Eventos</th><th>Atividade</th><th>Última atividade</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'
    return '<div class="taiga-student-grid">'+cards+'</div><details class="taiga-student-details"><summary>Ver comparação em tabela</summary>'+table+'</details>'


def _timeline(data: dict) -> str:
    rows=[]
    for event in (data.get("activity") or [])[:40]:
        actor=event.get("delegated_user_id") or event.get("actor_id") or "sistema";detail=event.get("attrs") or {}
        ref=detail.get("summary") or detail.get("sha") or detail.get("commit") or detail.get("task_ref") or ""
        rows.append(f'<tr><td>{h(_when(event.get("ts")))}</td><td>{h(actor)}</td><td><span class="chip">{h(event.get("source"))}</span></td><td>{h(event.get("action"))}</td><td>{h(ref)}</td></tr>')
    if not rows:return '<div class="resource-empty taiga-empty-compact"><h3>Sem atividade registrada</h3><p>Commits, Taiga e demais eventos aparecerão aqui conforme forem ocorrendo.</p></div>'
    return '<div class="table-scroll"><table class="cm-table taiga-table"><thead><tr><th>Quando</th><th>Usuário</th><th>Fonte</th><th>Ação</th><th>Referência</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'


def _integrations(data: dict) -> str:
    taiga=data.get("taiga") or {};faro=data.get("faro") or {};forgejo=data.get("forgejo") or {};private=data.get("taiga_project") or {}
    private_error=str(private.get("error") or "")
    private_note=(private.get("source") or ("Cliente do broker Faro não configurado" if not private.get("configured") else "Resumo privado do projeto indisponível" if private_error else "indisponível"))
    cards=(
        ("Taiga","Aplicação",bool(taiga.get("ok")),f'HTTP {taiga.get("http_status") or "—"} · OIDC institucional'),
        ("Faro","Runtime",bool(faro.get("ok")),f'{len(faro.get("containers") or [])} containers · coleta {_when(faro.get("updated_at"))}'),
        ("Forgejo","Automação",bool(forgejo.get("ok")),f'{forgejo.get("automation_status") or "sem evento"} · {_when(forgejo.get("automation_at"))}'),
        ("Broker","Dados privados",bool(private.get("ok")),str(private_note)),
    )
    return '<div class="taiga-integration-grid">'+''.join(f'<div class="taiga-integration"><div><span>{h(kicker)}</span><b>{h(title)}</b></div>{_status(ok,"OK","atenção")}<small>{h(note)}</small></div>' for kicker,title,ok,note in cards)+'</div>'


def _detail(data: dict) -> str:
    latest=(data.get("dashboard") or {}).get("latest_activity")
    audience='Todos os membros do projeto' if data.get('can_view_members') else 'Somente seus dados'
    return (
        _project_header(data)+_kpis(data)+
        '<div class="taiga-dashboard-grid">'
        '<section class="resource-card taiga-panel"><div class="taiga-panel-head"><div><p class="resource-kicker">Progresso</p><h3>Execução do projeto</h3></div><span class="chip">Taiga</span></div>'+_completion(data)+'</section>'
        '<section class="resource-card taiga-panel"><div class="taiga-panel-head"><div><p class="resource-kicker">Histórico</p><h3>Atividade nos últimos 14 dias</h3></div><small>Último evento '+h(_when(latest))+'</small></div>'+_history_chart(data)+'</section>'
        '<section class="resource-card taiga-panel"><div class="taiga-panel-head"><div><p class="resource-kicker">Origem dos eventos</p><h3>Integrações em atividade</h3></div></div>'+_source_chart(data)+'</section>'
        '<section class="resource-card taiga-panel"><div class="taiga-panel-head"><div><p class="resource-kicker">Plataforma</p><h3>Saúde das integrações</h3></div></div>'+_integrations(data)+'</section>'
        '</div>'
        '<section class="resource-section taiga-section"><div class="resource-section-head"><div><p class="ov-eyebrow">Acessos</p><h2>Últimos acessos e atividade</h2><p>'+h(audience)+' · tempo estimado a partir de eventos autenticados.</p></div></div>'+_recent_accesses(data)+'</section>'
        '<section class="resource-section taiga-section"><div class="resource-section-head"><div><p class="ov-eyebrow">Acompanhamento</p><h2>'+('Membros do projeto' if data.get('can_view_members') else 'Meus indicadores')+'</h2><p>Trabalho no Taiga e atividade acadêmica consolidados.</p></div></div>'+_members(data)+'</section>'
        '<section class="resource-section taiga-section"><div class="resource-section-head"><div><p class="ov-eyebrow">Linha do tempo</p><h2>Atividade recente</h2><p>Eventos normalizados de Taiga, Forgejo e Academic Audit. Commits não criam tarefas automaticamente.</p></div></div>'+_timeline(data)+'</section>'
        '<p class="resource-note taiga-footnote"><b>Atualização:</b> este painel é recalculado ao abrir ou recarregar o projeto a partir dos eventos já coletados em segundo plano. Atividade estimada é um indicador de uso da plataforma, não uma medição de horas trabalhadas.</p>'
    )


def taiga_body(data: dict) -> str:
    return _detail(data) if data.get("selected_project") else _catalog(data)
