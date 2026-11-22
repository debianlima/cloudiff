#!/usr/bin/env python3
"""T-044: read-only per-stage database card (W/H/P), evidence-based only.

Discovers databases from recorded runtime evidence (candidate/release
dependencies); never queries Docker, never reads or prints secrets and never
publishes database ports. Stages without evidence report honestly.
"""
import html

ENGINE_LABELS = {
    'postgresql': 'PostgreSQL', 'postgres': 'PostgreSQL',
    'mysql': 'MySQL', 'mariadb': 'MariaDB',
    'mongodb': 'MongoDB', 'mongo': 'MongoDB',
    'redis': 'Redis', 'sqlite': 'SQLite',
}
DB_KINDS = frozenset(ENGINE_LABELS)


def _deps(runtime_diff):
    try:
        deps = (runtime_diff or {}).get('dependencies') or []
        return [x for x in deps if isinstance(x, dict)]
    except Exception:
        return []


def _entry(dep):
    kind = str(dep.get('kind') or '').strip().lower()
    if kind not in DB_KINDS:
        return None
    return {
        'engine': ENGINE_LABELS[kind],
        'kind': kind,
        'database': str(dep.get('database') or dep.get('name') or ''),
    }


def stage_databases(candidates=(), releases=()):
    """Map stage code -> list of evidence-backed database entries.

    candidates: rows with stage_code/runtime_diff_json (W/H records).
    releases: rows with stage_code/detail_json (P records).
    """
    out = {}
    for row in candidates or []:
        stage = str(row.get('stage_code') or '').strip()
        if not stage:
            continue
        entries = [e for e in (_entry(d) for d in _deps(_json(row.get('runtime_diff_json')))) if e]
        if entries:
            out[stage] = entries
    for row in releases or []:
        stage = str(row.get('stage_code') or '').strip()
        if not stage or stage in out:
            continue
        runtime = _json(row.get('runtime_diff_json'))
        if not runtime:
            detail = _json(row.get('detail_json'))
            runtime = detail.get('runtime_diff') or detail.get('runtimeDiff') or {}
        entries = [e for e in (_entry(d) for d in _deps(runtime)) if e]
        if entries:
            out[stage] = entries
    return out


def _json(raw):
    import json
    try:
        return json.loads(raw or '{}') if isinstance(raw, str) else (raw or {})
    except Exception:
        return {}


def render(stage_map, selected_stage=''):
    """Read-only card; no credentials, no ports, no mutations."""
    stages = sorted(stage_map)
    if not stages:
        body = '<strong>Nenhum banco embutido detectado</strong><small>Fora do Supabase; nenhuma evidência de runtime registrada</small>'
    else:
        items = []
        for stage in stages:
            entries = stage_map[stage]
            desc = ' + '.join(e['engine'] + ((' · ' + e['database']) if e['database'] else '') for e in entries)
            mark = ' <b>(selecionado)</b>' if selected_stage and stage == selected_stage else ''
            items.append('<div class="small"><code>' + html.escape(stage) + '</code>' + mark + ': ' + html.escape(desc) + '</div>')
        body = ''.join(items) + '<small>Somente leitura · descoberto pelo runtime registrado · sem exposição de porta ou credencial</small>'
    return ('<div class="publication-info-card"><span>Banco por estágio</span>' + body + '</div>')
