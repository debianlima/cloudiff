"""Shared, read-only academic activity summary for project dashboards.

This module is deliberately UI-neutral.  It consolidates already-authorized
Taiga, Forgejo and Academic Audit facts without producing scores or rankings.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from portal.core.rbac import is_global
from portal.core.production_access import project_production_access

_AUDIT_URL=os.environ.get("CLOUDIF_AUDIT_URL","http://127.0.0.1:18201").rstrip("/")
_AUDIT_TOKEN=os.environ.get("CLOUDIF_AUDIT_TOKEN","").strip()
_FORJA_ENV=os.environ.get("CLOUDIF_FORJA_CLIENT_ENV","/etc/cloudif/forja-agent-client.env")
_TAIGA_RECONCILER_ENV=os.environ.get("CLOUDIF_TAIGA_RECONCILER_CLIENT_ENV","/etc/cloudif/taiga-reconciler-client.env")


def _read_env(path: str) -> dict[str,str]:
    out={}
    try:
        with open(path,encoding="utf-8",errors="ignore") as handle:
            for line in handle:
                line=line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key,value=line.split("=",1)
                out[key.strip()]=value.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


def _http_json(url: str, *, headers: dict[str,str] | None=None, timeout: float=5.0) -> tuple[int,Any]:
    req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"CloudIFF-Academic-Tracking/1.0",**(headers or {})})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as response:
            return int(response.status),json.load(response)
    except urllib.error.HTTPError as error:
        try:data=json.load(error)
        except Exception:data={"ok":False,"error":"upstream_http_error"}
        return int(error.code),data
    except Exception:
        return 503,{"ok":False,"error":"upstream_unavailable"}


def _parse_ts(value: Any) -> datetime | None:
    text=str(value or "").strip()
    if not text:return None
    try:
        stamp=datetime.fromisoformat(text.replace("Z","+00:00"))
        if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=timezone.utc)
        return stamp.astimezone(timezone.utc)
    except Exception:
        return None


def _recent(value: Any, days: int) -> bool:
    stamp=_parse_ts(value)
    return bool(stamp and stamp>=datetime.now(timezone.utc)-timedelta(days=max(1,int(days))))


def _audit_events(identity, slug: str) -> tuple[list[dict[str,Any]],bool]:
    if not _AUDIT_TOKEN:
        return [],False
    query={"project":slug,"limit":200}
    if not is_global(identity):query["subject"]=identity.username
    code,data=_http_json(_AUDIT_URL+"/v1/events?"+urllib.parse.urlencode(query),headers={"Authorization":"Bearer "+_AUDIT_TOKEN},timeout=5)
    if code!=200 or not isinstance(data,dict):return [],False
    out=[]
    for raw in data.get("events") or []:
        if not isinstance(raw,dict):continue
        out.append({
            "ts":raw.get("ts"),
            "actor":str(raw.get("delegated_user_id") or raw.get("actor_id") or "")[:128],
            "source":str(raw.get("source") or "")[:80],
            "action":str(raw.get("action") or "")[:120],
        })
    return out,True


def _forgejo_events(identity, slug: str) -> tuple[list[dict[str,Any]],bool]:
    cfg=_read_env(_FORJA_ENV);base=(cfg.get("FORJA_AGENT_URL") or "http://10.62.91.2:18095").rstrip("/");token=(cfg.get("FORJA_AGENT_TOKEN") or "").strip()
    if not token:return [],False
    code,data=_http_json(base+"/project/status?"+urllib.parse.urlencode({"slug":slug}),headers={"X-CloudIF-Token":token,"Authorization":"Bearer "+token},timeout=5)
    project=data.get("project") if isinstance(data,dict) else None
    if code!=200 or not isinstance(project,dict):return [],False
    out=[]
    for item in project.get("activity") or []:
        if not isinstance(item,dict):continue
        actor=str(item.get("actor") or "").strip()
        if not is_global(identity) and actor.lower()!=identity.username.strip().lower():continue
        out.append({"ts":item.get("ts"),"actor":actor[:128],"source":"forgejo","action":str(item.get("event") or item.get("action") or "activity")[:120]})
    return out,True


def _taiga_summary(identity, slug: str) -> tuple[dict[str,Any],bool]:
    cfg=_read_env(_TAIGA_RECONCILER_ENV);base=(cfg.get("TAIGA_RECONCILER_URL") or "").rstrip("/");token=(cfg.get("TAIGA_RECONCILER_TOKEN") or "").strip()
    if not base or not token:return {},False
    params={"subject":identity.username}
    if is_global(identity):params["include_members"]="1"
    code,data=_http_json(base+"/v1/projects/"+urllib.parse.quote(slug,safe="-._~")+"/summary?"+urllib.parse.urlencode(params),headers={"Authorization":"Bearer "+token},timeout=8)
    if code!=200 or not isinstance(data,dict) or not data.get("ok"):return {},False
    return data,True


def _channel(source: str) -> str:
    source=str(source or "").strip().lower()
    if "forgejo" in source or source in {"git","github"}:return "forgejo"
    if source=="taiga":return "taiga"
    if source=="project-access":return "environment"
    if source in {"mcp","portal","academic-audit"}:return "mcp"
    return source or "other"


def project_tracking_summary(identity, project: dict[str,Any]) -> dict[str,Any]:
    slug=str(project.get("slug") or "").strip()
    if not slug:return {"ok":False,"slug":"","error":"invalid_project"}
    audit,audit_ok=_audit_events(identity,slug)
    forgejo,forgejo_ok=_forgejo_events(identity,slug)
    taiga,taiga_ok=_taiga_summary(identity,slug)
    events=list(audit)+list(forgejo)
    timeline=taiga.get("timeline") if isinstance(taiga.get("timeline"),list) else []
    for item in timeline:
        if not isinstance(item,dict):continue
        events.append({"ts":item.get("ts"),"actor":str(item.get("actor") or "")[:128],"source":"taiga","action":str(item.get("type") or "activity")[:120]})
    events.sort(key=lambda item:str(item.get("ts") or ""),reverse=True)
    counts=taiga.get("counts") if isinstance(taiga.get("counts"),dict) else {}
    members=taiga.get("members") if isinstance(taiga.get("members"),list) else []
    members_total=int(counts.get("members") or len(members))
    last_by_user={}
    member_names=set()
    member_stamps=[]
    for member in members:
        if not isinstance(member,dict):continue
        actor=str(member.get("username") or "").strip().lower()
        if not actor:continue
        member_names.add(actor)
        stamp=max(str(member.get("last_activity") or ""),str(member.get("last_login") or ""))
        if stamp:
            last_by_user[actor]=stamp
            member_stamps.append(stamp)
    for event in events:
        actor=str(event.get("actor") or "").strip().lower()
        stamp=str(event.get("ts") or "")
        if actor and actor in member_names and stamp>last_by_user.get(actor,""):
            last_by_user[actor]=stamp
    active_7=sum(1 for actor in member_names if _recent(last_by_user.get(actor),7))
    recent14=[event for event in events if _recent(event.get("ts"),14)]
    channels=Counter(_channel(event.get("source")) for event in recent14)
    tasks=int(counts.get("tasks") or 0);tasks_closed=int(counts.get("tasks_closed") or 0)
    stories=int(counts.get("userstories") or 0);stories_closed=int(counts.get("userstories_closed") or 0)
    production=project_production_access(slug)
    return {
        "ok":bool(audit_ok or forgejo_ok or taiga_ok),
        "slug":slug,
        "name":str(project.get("name") or slug)[:200],
        "status":str(project.get("status") or "")[:80],
        "members":members_total,
        "active_7d":active_7,
        "without_activity_7d":max(0,members_total-active_7) if members_total else 0,
        "events_14d":len(recent14),
        "tasks_open":max(0,tasks-tasks_closed),
        "stories_open":max(0,stories-stories_closed),
        "last_activity":max([str(event.get("ts") or "") for event in events]+member_stamps,default=""),
        "channels_14d":{"taiga":int(channels.get("taiga",0)),"forgejo":int(channels.get("forgejo",0)),"mcp":int(channels.get("mcp",0)),"environment":int(channels.get("environment",0))},
        "production":production,
        "coverage":{"taiga":taiga_ok,"forgejo":forgejo_ok,"mcp":audit_ok,"environment_access":True,"production_access":bool(production.get("instrumented")),"external_authenticated_access":False},
    }
