"""Read-only Taiga/CloudIFF integration model.

The Portal remains the authorization boundary.  Project visibility comes from
portal.modules.projects.service, not from Taiga memberships.  External tokens
never leave the server process and returned data is deliberately summarized.
"""
from __future__ import annotations

import json
import os
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from portal.core.rbac import is_global
from portal.core.project_visibility import visible_projects as _visible_projects

_DB = os.environ.get("CLOUDIF_PORTAL_DB", "/var/lib/cloudif/portal/cloudif-portal.db")
_TAIGA_URL = os.environ.get("CLOUDIF_TAIGA_URL", "https://taiga.cloudiff.duckdns.org").rstrip("/")
_TAIGA_RECONCILER_ENV = os.environ.get("CLOUDIF_TAIGA_RECONCILER_CLIENT_ENV", "/etc/cloudif/taiga-reconciler-client.env")
_AUDIT_URL = os.environ.get("CLOUDIF_AUDIT_URL", "http://127.0.0.1:18201").rstrip("/")
_AUDIT_TOKEN = os.environ.get("CLOUDIF_AUDIT_TOKEN", "").strip()
_FORJA_ENV = os.environ.get("CLOUDIF_FORJA_CLIENT_ENV", "/etc/cloudif/forja-agent-client.env")
_SAFE_ATTRS = {"sha", "commit", "branch", "ref", "repository", "repo", "pull_request", "release", "version", "status", "task_ref", "summary", "tool", "delivery"}


def _read_env(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                out[key.strip()] = value.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


def _http_json(url: str, *, headers: dict[str, str] | None = None, timeout: float = 4.0) -> tuple[int, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "CloudIFF-Portal-Taiga/1.0", **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status), json.load(response)
    except urllib.error.HTTPError as error:
        try:
            data = json.load(error)
        except Exception:
            data = {"ok": False, "error": "upstream_http_error"}
        return int(error.code), data
    except Exception:
        return 503, {"ok": False, "error": "upstream_unavailable"}


def _taiga_public_health() -> dict[str, Any]:
    code, data = _http_json(_TAIGA_URL + "/api/v1/", timeout=4)
    return {
        "ok": code == 200 and isinstance(data, dict),
        "http_status": code,
        "url": _TAIGA_URL,
        "oidc": True,
    }


def _faro_taiga_telemetry() -> dict[str, Any]:
    try:
        con = sqlite3.connect(_DB)
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT node, ok, payload, updated_at FROM node_metrics_cache ORDER BY updated_at DESC").fetchall()
        con.close()
    except Exception:
        rows = []
    chosen = None
    payload: dict[str, Any] = {}
    for row in rows:
        try:
            candidate = json.loads(row["payload"] or "{}")
        except Exception:
            candidate = {}
        label = " ".join((str(row["node"] or ""), str(candidate.get("hostname") or ""))).lower()
        if "faro" in label:
            chosen, payload = row, candidate
            break
    if chosen is None:
        return {"ok": False, "node": "faro", "containers": [], "error": "faro_metrics_unavailable"}
    containers = []
    for item in ((payload.get("docker") or {}).get("containers") or []):
        name = str(item.get("name") or "")
        image = str(item.get("image") or "")
        if "taiga" not in (name + " " + image).lower():
            continue
        containers.append({"name": name[:160], "image": image[:200], "status": str(item.get("status") or "")[:160]})
    memory = payload.get("memory") or {}
    network = payload.get("network") or {}
    return {
        "ok": bool(chosen["ok"]),
        "node": str(chosen["node"] or "faro"),
        "updated_at": chosen["updated_at"],
        "containers": containers,
        "containers_ok": sum(1 for item in containers if "up " in item["status"].lower() or item["status"].lower().startswith("up")),
        "memory_used": memory.get("used"),
        "memory_total": memory.get("total"),
        "network_rx_bps": network.get("rx_bps"),
        "network_tx_bps": network.get("tx_bps"),
    }


def _forja_project(identity, slug: str) -> dict[str, Any]:
    cfg = _read_env(_FORJA_ENV)
    base = (cfg.get("FORJA_AGENT_URL") or "http://10.62.91.2:18095").rstrip("/")
    token = cfg.get("FORJA_AGENT_TOKEN") or ""
    if not token:
        return {"ok": False, "error": "forja_credentials_unconfigured"}
    query = urllib.parse.urlencode({"slug": slug})
    code, data = _http_json(base + "/project/status?" + query, headers={"X-CloudIF-Token": token, "Authorization": "Bearer " + token}, timeout=5)
    project = data.get("project") if isinstance(data, dict) else None
    if code != 200 or not isinstance(project, dict):
        return {"ok": False, "error": "forja_project_unavailable", "http_status": code}
    forgejo = project.get("forgejo") if isinstance(project.get("forgejo"), dict) else {}
    activity = [item for item in (project.get("activity") or []) if isinstance(item, dict)]
    if not is_global(identity):
        activity = [item for item in activity if str(item.get("actor") or "").strip().lower() == identity.username.strip().lower()]
    activity = [{k: item.get(k) for k in ("ts","source","event","actor","action","ref","commit","number","version","summary","result","delivery") if item.get(k) not in (None, "")} for item in activity[-100:]]
    return {
        "ok": True,
        "automation_at": project.get("last_forgejo_automation_at"),
        "automation_status": project.get("last_forgejo_automation_status"),
        "automation_ok": project.get("last_forgejo_automation_ok"),
        "commit": str(project.get("last_forgejo_automation_commit") or "")[:64],
        "repo_url": str(forgejo.get("url") or project.get("repo_url") or "")[:500],
        "membership_reconciled_at": project.get("membership_reconciled_at"),
        "activity": activity,
    }


def _safe_attrs(event: dict[str, Any]) -> dict[str, Any]:
    attrs = event.get("attrs")
    if not isinstance(attrs, dict):
        try:
            attrs = json.loads(event.get("attrs_json") or "{}")
        except Exception:
            attrs = {}
    out = {}
    for key in _SAFE_ATTRS:
        if key not in attrs:
            continue
        value = attrs[key]
        if isinstance(value, (str, int, float, bool)) or value is None:
            out[key] = value[:500] if isinstance(value, str) else value
    return out


def _audit_events(identity, slug: str, limit: int = 100) -> tuple[list[dict[str, Any]], str]:
    if not _AUDIT_TOKEN:
        return [], "audit_credentials_unconfigured"
    query: dict[str, str | int] = {"project": slug, "limit": max(1, min(limit, 200))}
    if not is_global(identity):
        query["subject"] = identity.username
    code, data = _http_json(_AUDIT_URL + "/v1/events?" + urllib.parse.urlencode(query), headers={"Authorization": "Bearer " + _AUDIT_TOKEN}, timeout=5)
    if code != 200 or not isinstance(data, dict):
        return [], "audit_unavailable"
    events = []
    for raw in data.get("events") or []:
        if not isinstance(raw, dict):
            continue
        events.append({
            "ts": raw.get("ts"),
            "actor_id": str(raw.get("actor_id") or raw.get("delegated_user_id") or "")[:128],
            "delegated_user_id": str(raw.get("delegated_user_id") or "")[:128],
            "source": str(raw.get("source") or "")[:80],
            "action": str(raw.get("action") or "")[:120],
            "result": str(raw.get("result") or "")[:40],
            "duration_ms": int(raw.get("duration_ms") or 0),
            "attrs": _safe_attrs(raw),
        })
    return events, "ok"


def _http_json_post(url: str, payload: dict[str, Any], *, headers: dict[str, str] | None = None, timeout: float = 8.0) -> tuple[int, Any]:
    body=json.dumps(payload,ensure_ascii=False,separators=(",", ":")).encode("utf-8")
    request=urllib.request.Request(url,data=body,method="POST",headers={"Accept":"application/json","Content-Type":"application/json","User-Agent":"CloudIFF-Portal-Taiga/1.0",**(headers or {})})
    try:
        with urllib.request.urlopen(request,timeout=timeout) as response:
            return int(response.status),json.load(response)
    except urllib.error.HTTPError as error:
        try:data=json.load(error)
        except Exception:data={"ok":False,"error":"upstream_http_error"}
        return int(error.code),data
    except Exception:
        return 503,{"ok":False,"error":"upstream_unavailable"}


def grant_taiga_access(identity, slug: str) -> dict[str, Any]:
    slug=str(slug or "").strip().lower()
    if not is_global(identity):
        return {"ok":False,"status":403,"error":"forbidden"}
    allowed={str(p.get("slug") or ""):p for p in _visible_projects(identity,_DB)}
    if slug not in allowed:
        return {"ok":False,"status":403,"error":"project_not_visible"}
    email=str(identity.email or "").strip().lower()
    if not email:
        return {"ok":False,"status":409,"error":"identity_email_required"}
    cfg=_read_env(_TAIGA_RECONCILER_ENV);base=(cfg.get("TAIGA_RECONCILER_URL") or "").rstrip("/");token=(cfg.get("TAIGA_RECONCILER_TOKEN") or "").strip()
    if not base or not token:
        return {"ok":False,"status":503,"error":"taiga_reconciler_credentials_unconfigured"}
    url=base+"/v1/projects/"+urllib.parse.quote(slug,safe="-._~")+"/access/grant"
    code,data=_http_json_post(url,{"username":identity.username,"email":email,"full_name":identity.username},headers={"Authorization":"Bearer "+token},timeout=15)
    if code!=200 or not isinstance(data,dict) or not data.get("ok"):
        return {"ok":False,"status":code if code in {400,404,409} else 503,"error":str((data or {}).get("error") if isinstance(data,dict) else "taiga_grant_failed")}
    return {"ok":True,"status":200,"slug":slug,"taiga_username":str(data.get("taiga_username") or identity.username)[:150],"redirect":_TAIGA_URL+"/cloudif-enter/"+urllib.parse.quote(slug,safe="-._~"),"created_user":bool(data.get("created_user")),"created_membership":bool(data.get("created_membership")),"secrets_exposed":False}


def _taiga_private_summary(identity, slug: str) -> dict[str, Any]:
    cfg = _read_env(_TAIGA_RECONCILER_ENV)
    base = (cfg.get("TAIGA_RECONCILER_URL") or "").rstrip("/")
    token = (cfg.get("TAIGA_RECONCILER_TOKEN") or "").strip()
    if not base or not token:
        return {"configured": False, "ok": False, "error": "taiga_reconciler_credentials_unconfigured"}
    query: dict[str, str] = {"include_members": "1" if is_global(identity) else "0"}
    if not is_global(identity):
        query["subject"] = identity.username
    url = base + "/v1/projects/" + urllib.parse.quote(slug, safe="-._~") + "/summary?" + urllib.parse.urlencode(query)
    code, data = _http_json(url, headers={"Authorization": "Bearer " + token}, timeout=12)
    if code != 200 or not isinstance(data, dict) or not data.get("ok"):
        return {"configured": True, "ok": False, "error": "taiga_reconciler_unavailable", "http_status": code}
    project = data.get("project") if isinstance(data.get("project"), dict) else {}
    counts = data.get("counts") if isinstance(data.get("counts"), dict) else {}
    subject = data.get("subject") if isinstance(data.get("subject"), dict) else None
    members = data.get("members") if is_global(identity) and isinstance(data.get("members"), list) else []
    timeline = data.get("timeline") if isinstance(data.get("timeline"), list) else []
    return {
        "configured": True,
        "ok": True,
        "project": {"id": project.get("id"), "slug": str(project.get("slug") or slug), "name": str(project.get("name") or slug)[:200]},
        "counts": {k: counts.get(k) for k in ("tasks", "tasks_closed", "userstories", "userstories_closed", "milestones", "milestones_closed", "members")},
        "subject": subject,
        "members": members,
        "timeline": timeline[:100],
        "url": _TAIGA_URL + "/cloudif-enter/" + urllib.parse.quote(str(project.get("slug") or slug), safe="-._~"),
        "source": "faro-reconciler",
    }


def _parse_ts(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def _estimated_active_minutes(events: list[dict[str, Any]], actor: str) -> int:
    actor = actor.strip().lower()
    stamps = []
    for event in events:
        event_actor = str(event.get("delegated_user_id") or event.get("actor_id") or "").strip().lower()
        if event_actor != actor:
            continue
        stamp = _parse_ts(event.get("ts"))
        if stamp:
            stamps.append(stamp)
    stamps.sort()
    if not stamps:
        return 0
    minutes = 1
    for left, right in zip(stamps, stamps[1:]):
        delta = max(0.0, (right - left).total_seconds() / 60.0)
        minutes += int(min(delta, 15.0))
    return minutes


def _actor_summary(events: list[dict[str, Any]], taiga_members: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    counts: dict[str, Counter] = defaultdict(Counter)
    last: dict[str, str] = {}
    members = {str(item.get("username") or "").strip().lower(): item for item in (taiga_members or []) if isinstance(item, dict) and str(item.get("username") or "").strip()}
    for event in events:
        actor = (event.get("delegated_user_id") or event.get("actor_id") or "").strip().lower()
        if not actor or actor in {"system", "portal", "mcp", "forgejo-webhook"}:
            continue
        counts[actor][event.get("source") or "other"] += 1
        counts[actor]["total"] += 1
        stamp = str(event.get("ts") or "")
        if stamp > last.get(actor, ""):
            last[actor] = stamp
    users = sorted(set(counts) | set(members))
    out = []
    for actor in users:
        item = members.get(actor) or {}
        out.append({
            "username": actor,
            "full_name": str(item.get("full_name") or actor)[:200],
            "role": str(item.get("role") or "")[:120],
            "total": counts[actor]["total"],
            "sources": dict(counts[actor]),
            "last_activity": max(last.get(actor, ""), str(item.get("last_activity") or "")),
            "last_login": item.get("last_login"),
            "tasks_assigned": int(item.get("tasks_assigned") or 0),
            "tasks_closed": int(item.get("tasks_closed") or 0),
            "stories_assigned": int(item.get("stories_assigned") or 0),
            "stories_closed": int(item.get("stories_closed") or 0),
            "estimated_active_minutes": _estimated_active_minutes(events, actor),
        })
    return out


def _activity_history(events: list[dict[str, Any]], days: int = 14) -> list[dict[str, Any]]:
    days=max(7,min(int(days or 14),31))
    parsed=[stamp for stamp in (_parse_ts(item.get("ts")) for item in events) if stamp]
    end=(max(parsed) if parsed else datetime.now(timezone.utc)).astimezone(timezone.utc).date()
    start=end-timedelta(days=days-1)
    buckets={start+timedelta(days=i):{"events":0,"actors":set()} for i in range(days)}
    for event in events:
        stamp=_parse_ts(event.get("ts"))
        if not stamp:
            continue
        day=stamp.astimezone(timezone.utc).date()
        if day not in buckets:
            continue
        buckets[day]["events"]+=1
        actor=str(event.get("delegated_user_id") or event.get("actor_id") or "").strip().lower()
        if actor and actor not in {"system","portal","mcp","forgejo-webhook"}:
            buckets[day]["actors"].add(actor)
    return [{"date":day.isoformat(),"label":day.strftime("%d/%m"),"events":value["events"],"actors":len(value["actors"])} for day,value in sorted(buckets.items())]


def _source_breakdown(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labels={"forgejo":"Forgejo","taiga":"Taiga","mcp":"MCP","portal":"Portal","academic-audit":"Academic Audit"}
    counter=Counter(str(item.get("source") or "other").strip().lower() for item in events)
    total=sum(counter.values()) or 1
    out=[]
    for source,count in counter.most_common():
        out.append({"source":source,"label":labels.get(source,source.replace("-"," ").title()),"count":count,"pct":round(100*count/total)})
    return out


def _completion_summary(taiga_project: dict[str, Any]) -> list[dict[str, Any]]:
    counts=taiga_project.get("counts") if isinstance(taiga_project.get("counts"),dict) else {}
    rows=[]
    for key,closed_key,label in (("tasks","tasks_closed","Tarefas"),("userstories","userstories_closed","Histórias"),("milestones","milestones_closed","Etapas")):
        total=int(counts.get(key) or 0);closed=int(counts.get(closed_key) or 0)
        rows.append({"key":key,"label":label,"total":total,"closed":closed,"open":max(0,total-closed),"pct":round(100*closed/total) if total else 0})
    return rows


def _recent_accesses(identity, actors: list[dict[str, Any]], subject: dict[str, Any] | None) -> list[dict[str, Any]]:
    if is_global(identity):
        rows=[dict(item) for item in actors]
    elif subject:
        rows=[{
            "username":identity.username,
            "full_name":str(subject.get("full_name") or identity.username)[:200],
            "role":str(subject.get("role") or "")[:120],
            "last_login":subject.get("last_login"),
            "last_activity":subject.get("last_activity"),
            "estimated_active_minutes":int(subject.get("estimated_active_minutes") or 0),
            "total":int(subject.get("history_events") or 0),
        }]
    else:
        rows=[]
    rows.sort(key=lambda item:max(str(item.get("last_activity") or ""),str(item.get("last_login") or "")),reverse=True)
    return rows[:20]


def _dashboard_metrics(identity, events: list[dict[str, Any]], actors: list[dict[str, Any]], subject: dict[str, Any] | None, taiga_project: dict[str, Any]) -> dict[str, Any]:
    user_ids={str(item.get("delegated_user_id") or item.get("actor_id") or "").strip().lower() for item in events}
    user_ids={item for item in user_ids if item and item not in {"system","portal","mcp","forgejo-webhook"}}
    latest=max((str(item.get("ts") or "") for item in events),default="")
    return {
        "activity_total":len(events),
        "active_users":len(user_ids),
        "latest_activity":latest,
        "history":_activity_history(events,14),
        "sources":_source_breakdown(events),
        "completion":_completion_summary(taiga_project),
        "recent_accesses":_recent_accesses(identity,actors,subject),
    }


def taiga_data(identity, selected_slug: str = "") -> dict[str, Any]:
    projects = _visible_projects(identity, _DB)
    allowed = {str(p.get("slug") or ""): p for p in projects}
    slug = selected_slug if selected_slug in allowed else ""
    selected = allowed.get(slug)
    taiga_health=_taiga_public_health()
    faro=_faro_taiga_telemetry()
    if not slug:
        return {
            "username":identity.username,
            "can_view_members":is_global(identity),
            "projects":projects,
            "project_count":len(projects),
            "selected_project":None,
            "taiga":taiga_health,
            "faro":faro,
            "forgejo":{"ok":False,"error":"no_project","activity":[]},
            "taiga_project":{"configured":bool(_read_env(_TAIGA_RECONCILER_ENV).get("TAIGA_RECONCILER_TOKEN")),"ok":False,"error":"no_project"},
            "activity":[],
            "activity_state":"no_project",
            "actors":[],
            "subject":None,
            "dashboard":{"activity_total":0,"active_users":0,"latest_activity":"","history":[],"sources":[],"completion":[],"recent_accesses":[]},
            "privacy":{"individual_scope":"all-project-members" if is_global(identity) else "self","activity_is_estimated":True},
        }
    events, audit_state = _audit_events(identity, slug)
    forgejo = _forja_project(identity, slug)
    taiga_project = _taiga_private_summary(identity, slug)
    for item in forgejo.get("activity") or []:
        events.append({"ts": item.get("ts"), "actor_id": item.get("actor") or "", "delegated_user_id": "", "source": item.get("source") or "forgejo", "action": item.get("event") or item.get("action") or "activity", "result": item.get("result") or "success", "duration_ms": 0, "attrs": {k: item.get(k) for k in ("summary","commit","ref","number","version","delivery") if item.get(k) not in (None, "")}})
    for item in taiga_project.get("timeline") or []:
        if not isinstance(item, dict):
            continue
        events.append({"ts": item.get("ts"), "actor_id": str(item.get("actor") or "")[:128], "delegated_user_id": "", "source": "taiga", "action": str(item.get("type") or "activity")[:120], "result": "success", "duration_ms": 0, "attrs": {"task_ref": str(item.get("key") or "")[:180]}})
    events.sort(key=lambda item: str(item.get("ts") or ""), reverse=True)
    actors = _actor_summary(events, taiga_project.get("members") or []) if is_global(identity) else []
    subject = taiga_project.get("subject") if isinstance(taiga_project.get("subject"), dict) else None
    if subject is not None:
        subject = {**subject, "estimated_active_minutes": _estimated_active_minutes(events, identity.username)}
    dashboard=_dashboard_metrics(identity,events,actors,subject,taiga_project)
    return {
        "username": identity.username,
        "can_view_members": is_global(identity),
        "projects": projects,
        "project_count":len(projects),
        "selected_project": selected,
        "taiga": taiga_health,
        "faro": faro,
        "forgejo": forgejo,
        "taiga_project": taiga_project,
        "activity": events,
        "activity_state": audit_state,
        "actors": actors,
        "subject": subject,
        "dashboard":dashboard,
        "privacy": {"individual_scope": "all-project-members" if is_global(identity) else "self", "activity_is_estimated": True},
    }
