"""HTML for the Taiga project telemetry module."""
from __future__ import annotations

import html
from urllib.parse import quote

BASE = "/cloudiff/portal"
TAIGA = "https://taiga.cloudiff.duckdns.org"


def h(value) -> str:
    return html.escape(str(value or ""), quote=True)


def _status(ok: bool, yes: str = "Disponível", no: str = "Atenção") -> str:
    return f'<span class="chip{'' if ok else ' is-drift'}">{h(yes if ok else no)}</span>'


def _project_picker(data: dict) -> str:
    selected = (data.get("selected_project") or {}).get("slug") or ""
    cards = []
    for project in data.get("projects") or []:
        slug = str(project.get("slug") or "")
        current = ' aria-current="page"' if slug == selected else ""
        cards.append(
            '<article class="resource-card">'
            f'<div class="resource-card-head"><div><p class="resource-kicker">Projeto</p><h3>{h(project.get("name") or slug)}</h3></div>'
            f'<span class="chip">{h(slug)}</span></div>'
            f'<p class="resource-note">{h(project.get("description") or "Projeto autorizado pela ACL CloudIFF.")}</p>'
            f'<a class="btn btn-quiet" href="{BASE}/?tab=taiga&amp;project={quote(slug, safe="")}"{current}>Acompanhar no Taiga</a>'
            '</article>'
        )
    if not cards:
        return '<div class="resource-empty"><h3>Nenhum projeto visível</h3><p>O Taiga respeita a mesma ACL do Portal.</p></div>'
    return '<div class="resource-grid">' + ''.join(cards) + '</div>'


def _integration_cards(data: dict) -> str:
    taiga = data.get("taiga") or {}; faro = data.get("faro") or {}; forgejo = data.get("forgejo") or {}; private = data.get("taiga_project") or {}
    private_label = "Dados privados conectados" if private.get("ok") else ("Credencial server-side pendente" if not private.get("configured") else "Projeto não localizado")
    return '<div class="resource-grid">' + ''.join((
        f'<article class="resource-card"><div class="resource-card-head"><div><p class="resource-kicker">Taiga</p><h3>Aplicação</h3></div>{_status(bool(taiga.get("ok")))}</div><p class="resource-note">API pública HTTP {h(taiga.get("http_status"))}. Login institucional via OIDC.</p><a class="btn btn-quiet" target="_blank" rel="noopener" href="{TAIGA}">Abrir no Taiga</a></article>',
        f'<article class="resource-card"><div class="resource-card-head"><div><p class="resource-kicker">Faro</p><h3>Stack Taiga</h3></div>{_status(bool(faro.get("ok")))}</div><p class="resource-note">{len(faro.get("containers") or [])} container(s) Taiga observados · coleta {h(faro.get("updated_at") or "indisponível")}.</p></article>',
        f'<article class="resource-card"><div class="resource-card-head"><div><p class="resource-kicker">Forgejo</p><h3>Automação do projeto</h3></div>{_status(bool(forgejo.get("ok")))}</div><p class="resource-note">Último ciclo: {h(forgejo.get("automation_status") or "sem evento")} · {h(forgejo.get("automation_at") or "—")}.</p></article>',
        f'<article class="resource-card"><div class="resource-card-head"><div><p class="resource-kicker">Integração privada</p><h3>Taiga por projeto</h3></div>{_status(bool(private.get("ok")),"Conectada","Pendente")}</div><p class="resource-note">{h(private_label)}</p></article>',
    )) + '</div>'


def _taiga_counts(data: dict) -> str:
    item = data.get("taiga_project") or {}
    if not item.get("ok"):
        return '<div class="resource-empty"><h3>Resumo privado do Taiga ainda indisponível</h3><p>A tela já está integrada à ACL, Forgejo, Academic Audit e telemetria do Faro. Tarefas e etapas entram automaticamente quando a credencial server-side do Taiga for materializada no ambiente.</p></div>'
    counts = item.get("counts") or {}
    labels = (("Tarefas", counts.get("tasks")), ("Histórias", counts.get("userstories")), ("Etapas", counts.get("milestones")), ("Membros", counts.get("members")))
    cards = ''.join(f'<div class="ov-agg"><span>{h(label)}</span><b>{h(value if value is not None else "—")}</b></div>' for label, value in labels)
    return f'<div class="ov-aggs">{cards}</div><p><a class="btn" target="_blank" rel="noopener" href="{h(item.get("url") or TAIGA)}">Abrir este projeto no Taiga</a></p>'


def _activity(data: dict) -> str:
    rows = []
    for event in (data.get("activity") or [])[:100]:
        actor = event.get("delegated_user_id") or event.get("actor_id") or "sistema"
        detail = event.get("attrs") or {}
        ref = detail.get("summary") or detail.get("sha") or detail.get("commit") or detail.get("task_ref") or ""
        rows.append(f'<tr><td>{h(event.get("ts"))}</td><td>{h(actor)}</td><td>{h(event.get("source"))}</td><td>{h(event.get("action"))}</td><td>{h(ref)}</td><td>{h(event.get("result"))}</td></tr>')
    if not rows:
        return '<div class="resource-empty"><h3>Sem atividade acadêmica registrada</h3><p>Os eventos aparecerão aqui conforme MCP, Forgejo e Taiga publicarem no Academic Audit.</p></div>'
    return '<div class="table-scroll"><table class="cm-table"><thead><tr><th>Quando</th><th>Usuário</th><th>Fonte</th><th>Ação</th><th>Referência</th><th>Resultado</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>'


def _actors(data: dict) -> str:
    if not data.get("can_view_members"):
        return '<p class="resource-note">Sua visão individual mostra somente eventos associados ao seu usuário institucional.</p>'
    actors = data.get("actors") or []
    if not actors:
        return '<p class="resource-note">Ainda não há atividade individual normalizada para os membros deste projeto.</p>'
    rows = ''.join(f'<tr><td>{h(a.get("username"))}</td><td>{h(a.get("total"))}</td><td>{h(a.get("last_activity"))}</td></tr>' for a in actors)
    return '<div class="table-scroll"><table class="cm-table"><thead><tr><th>Usuário</th><th>Eventos</th><th>Última atividade</th></tr></thead><tbody>' + rows + '</tbody></table></div>'


def taiga_body(data: dict) -> str:
    project = data.get("selected_project") or {}
    title = h(project.get("name") or project.get("slug") or "Selecione um projeto")
    return f'''
<section class="resource-section" aria-labelledby="taiga-projects"><div class="resource-section-head"><div><p class="ov-eyebrow">Gestão acadêmica</p><h2 id="taiga-projects">Projetos no Taiga</h2><p>Mesma visibilidade e permissionamento dos projetos CloudIFF. Nenhuma ACL é duplicada aqui.</p></div></div>{_project_picker(data)}</section>
<section class="resource-section"><div class="resource-section-head"><div><p class="ov-eyebrow">Integrações</p><h2>{title}</h2><p>Saúde da aplicação, stack no Faro, Forgejo e leitura privada do Taiga.</p></div></div>{_integration_cards(data)}</section>
<section class="resource-section"><div class="resource-section-head"><div><p class="ov-eyebrow">Acompanhamento</p><h2>Etapas e trabalho</h2><p>Contadores vêm do Taiga quando a credencial server-side está disponível.</p></div></div>{_taiga_counts(data)}</section>
<section class="resource-section"><div class="resource-section-head"><div><p class="ov-eyebrow">Timeline</p><h2>Atividade do projeto</h2><p>Eventos normalizados; commits não criam tarefas automaticamente.</p></div></div>{_activity(data)}</section>
<section class="resource-section"><div class="resource-section-head"><div><p class="ov-eyebrow">Acompanhamento individual</p><h2>{'Alunos do projeto' if data.get('can_view_members') else 'Meus dados'}</h2><p>Professor/admin veem membros do projeto; alunos veem somente sua própria atividade autenticada.</p></div></div>{_actors(data)}<p class="resource-note">Tempo de atividade, quando disponível, é estimado a partir de eventos autenticados e não representa horas trabalhadas.</p></section>
'''
