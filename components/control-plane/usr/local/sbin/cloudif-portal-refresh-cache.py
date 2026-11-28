#!/usr/bin/env python3
import csv, datetime, json, os, sqlite3, subprocess, urllib.request, sys, fcntl
from pathlib import Path

BASE = Path(os.environ.get("CLOUDIF_BASE", "/srv/cloudif"))
DB = Path(os.environ.get("CLOUDIF_PORTAL_DB", "/var/lib/cloudif/portal/cloudif-portal.db"))
NODES = os.environ.get("CLOUDIF_NODES", "")
LIFECYCLE_LOCK = Path("/run/cloudif/portal-publication-lifecycle.lock")

DB.parent.mkdir(parents=True, exist_ok=True)

def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS projects(
      slug TEXT PRIMARY KEY,
      name TEXT,
      tenant TEXT,
      owner TEXT,
      description TEXT,
      repo_url TEXT,
      komodo_status TEXT DEFAULT 'not_configured',
      created_at TEXT,
      updated_at TEXT
    );

    CREATE TABLE IF NOT EXISTS project_acl(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      slug TEXT,
      subject_type TEXT,
      subject TEXT,
      UNIQUE(slug, subject_type, subject)
    );

    CREATE TABLE IF NOT EXISTS tenant_acl(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant TEXT,
      subject_type TEXT,
      subject TEXT,
      UNIQUE(tenant, subject_type, subject)
    );

    CREATE TABLE IF NOT EXISTS tenant_policy(
      tenant TEXT PRIMARY KEY,
      always_alive INTEGER DEFAULT 0,
      keepalive_until TEXT,
      max_hours INTEGER DEFAULT 6,
      updated_at TEXT
    );

    CREATE TABLE IF NOT EXISTS settings(
      key TEXT PRIMARY KEY,
      value TEXT,
      description TEXT,
      admin_only INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS action_log(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ts TEXT,
      actor TEXT,
      action TEXT,
      target TEXT,
      rc INTEGER,
      stdout TEXT,
      stderr TEXT
    );

    CREATE TABLE IF NOT EXISTS node_metrics_cache(
      node TEXT PRIMARY KEY,
      url TEXT,
      ok INTEGER,
      payload TEXT,
      updated_at TEXT
    );
    """)
    defaults = [
        ("SUPABASE_DISABLE_SIGNUP", "false", "Controla se novos usuários podem se cadastrar no Auth do Supabase."),
        ("SUPABASE_ENABLE_EMAIL_AUTOCONFIRM", "true", "Confirma e-mail automaticamente em ambiente didático."),
        ("CLOUDIF_MAX_STUDENT_KEEPALIVE_HOURS", "6", "Limite máximo que usuário pode manter banco ligado temporariamente."),
        ("CLOUDIF_ALLOW_GIT_ONLY_PROJECT", "true", "Permite projeto Git/Komodo sem banco Supabase vinculado."),
    ]
    for k, v, d in defaults:
        con.execute(
            "INSERT OR IGNORE INTO settings(key,value,description,admin_only) VALUES(?,?,?,1)",
            (k, v, d),
        )
    con.commit()
    con.close()

def fetch_json(url, timeout=5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return {"ok": True, "data": json.loads(r.read().decode())}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def network_rate(previous_payload, previous_updated_at, current_payload, current_updated_at):
    """Calculate bytes/second between two successful node samples."""
    try:
        previous = (previous_payload or {}).get("network") or {}
        current = (current_payload or {}).get("network") or {}
        before = datetime.datetime.fromisoformat(str(previous_updated_at).replace("Z", "+00:00"))
        after = datetime.datetime.fromisoformat(str(current_updated_at).replace("Z", "+00:00"))
        if before.tzinfo is None:
            before = before.replace(tzinfo=datetime.timezone.utc)
        if after.tzinfo is None:
            after = after.replace(tzinfo=datetime.timezone.utc)
        elapsed = (after - before).total_seconds()
        rx_delta = int(current.get("rx_bytes") or 0) - int(previous.get("rx_bytes") or 0)
        tx_delta = int(current.get("tx_bytes") or 0) - int(previous.get("tx_bytes") or 0)
        if elapsed <= 0 or rx_delta < 0 or tx_delta < 0:
            return None
        return {
            "sample_seconds": round(elapsed, 3),
            "rx_bps": round(rx_delta / elapsed, 2),
            "tx_bps": round(tx_delta / elapsed, 2),
            "total_bps": round((rx_delta + tx_delta) / elapsed, 2),
        }
    except (AttributeError, TypeError, ValueError):
        return None

def refresh_nodes():
    samples=[]
    for item in NODES.split(","):
        if "=" not in item:continue
        name,url=item.split("=",1);name=name.strip();url=url.strip().rstrip("/")+"/metrics"
        con=db();previous_row=con.execute("SELECT payload, updated_at FROM node_metrics_cache WHERE node=?",(name,)).fetchone();con.close()
        result=fetch_json(url,15);payload=result.get("data") if result.get("ok") else result;sampled_at=now_iso()
        if result.get("ok") and isinstance(payload,dict) and previous_row:
            try:previous_payload=json.loads(previous_row["payload"] or "{}")
            except Exception:previous_payload={}
            rate=network_rate(previous_payload,previous_row["updated_at"],payload,sampled_at)
            if rate:payload.setdefault("network",{}).update(rate)
        samples.append((name,url,1 if result.get("ok") else 0,json.dumps(payload,ensure_ascii=False),sampled_at))
    if not samples:return
    con=db()
    try:
        con.executemany("""INSERT INTO node_metrics_cache(node,url,ok,payload,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(node) DO UPDATE SET url=excluded.url,ok=excluded.ok,payload=excluded.payload,updated_at=excluded.updated_at""",samples);con.commit()
    finally:con.close()

def tenants_registry():
    reg = BASE / "registry" / "tenants.csv"
    if not reg.exists():
        return []
    with reg.open(errors="ignore") as f:
        return list(csv.DictReader(f))

def refresh_tenants():
    con = db()
    for r in tenants_registry():
        tenant = r.get("tenant") or ""
        if not tenant:
            continue
        con.execute("""
          INSERT OR IGNORE INTO tenant_policy(tenant,always_alive,max_hours,updated_at)
          VALUES(?,0,6,?)
        """, (tenant, now_iso()))
        if tenant in ["akadmin"]:
            con.execute("""
              UPDATE tenant_policy
              SET always_alive=1, max_hours=24, updated_at=?
              WHERE tenant=?
            """, (now_iso(), tenant))
    con.commit()
    con.close()


def public_project_catalog():
    con=db();con.row_factory=sqlite3.Row
    try:
        ids=[dict(r) for r in con.execute('''select i.project_slug,i.public_number,i.created_at,i.updated_at
          from project_public_ids i join projects p on p.slug=i.project_slug order by i.public_number''')]
    except Exception:
        ids=[]
    try:integrations={str(r['project']):dict(r) for r in con.execute('select * from project_integrations')}
    except Exception:integrations={}
    try:aliases={str(r['project_slug']):str(r['alias'] or '') for r in con.execute('select project_slug,alias from project_publication_aliases')}
    except Exception:aliases={}
    try:previews={str(r['project_slug']):dict(r) for r in con.execute('select * from project_preview_source_links')}
    except Exception:previews={}
    con.close();out=[]
    for item in ids:
        slug=str(item.get('project_slug') or '');integ=integrations.get(slug) or {};preview=previews.get(slug) or {}
        out.append({
          'slug':slug,'public_number':int(item.get('public_number') or 0),'alias':aliases.get(slug,''),'lifecycle':'current',
          'integration_status':str(integ.get('status') or ''),'forgejo_status':str(integ.get('forgejo_status') or ''),'komodo_status':str(integ.get('komodo_status') or ''),'supabase_status':str(integ.get('supabase_status') or ''),
          'preview_stage':str(preview.get('stage_code') or ''),'preview_status':str(preview.get('status') or ''),'preview_url':str(preview.get('url') or ''),
        })
    return out

def reserved_public_numbers():
    con=db();con.row_factory=sqlite3.Row
    try:
        rows=[dict(r) for r in con.execute('''select i.project_slug,i.public_number,i.created_at,i.updated_at
          from project_public_ids i left join projects p on p.slug=i.project_slug
          where p.slug is null order by i.public_number''')]
    except Exception:
        rows=[]
    finally:con.close()
    return [{'slug':str(r.get('project_slug') or ''),'public_number':int(r.get('public_number') or 0),'lifecycle':'reserved-deleted'} for r in rows]

def cache_approval_rows(rm,code,data):
    if code!=200 or not isinstance(data,dict) or not data.get('ok') or not isinstance(data.get('approvals'),list):
        return False
    rows=data['approvals']
    rm.approval_index_replace(rows)
    rm.put('approvals','rows',rows,'timer')
    return True

def refresh_portal_readmodels():
    for lib in ('/srv/cloudif/app-pointers/portal-current','/srv/cloudif/lib'):
        if lib not in sys.path:sys.path.insert(0,lib)
    try:
        import cloudif_portal_readmodel as rm
        from cloudif_ui_data import discover_projects
        import cloudif_ui_publications as publications
        import cloudif_project_provision_status as provision
        import cloudif_project_identity_panel as identities
        import cloudif_approval_panel as approvals
    except Exception as exc:
        print('WARN: readmodel imports',type(exc).__name__);return
    try:
        rm.put('tenants','registry',tenants_registry(),'timer')
    except Exception as exc:print('WARN: tenants readmodel',type(exc).__name__)
    try:
        rm.put('projects','public-catalog',public_project_catalog(),'timer');rm.put('projects','reserved-public-numbers',reserved_public_numbers(),'timer')
    except Exception as exc:print('WARN: public project catalog',type(exc).__name__)
    try:
        projects=discover_projects() or [];rm.put('projects','discovered',projects,'timer')
    except Exception as exc:
        projects=[];print('WARN: projects readmodel',type(exc).__name__)
    for item in projects:
        slug=str(item.get('slug') or '').strip()
        if not slug:continue
        try:
            job=provision.status(slug)
            state={'status':str(job.get('status') or ('not_started' if not job.get('ok') else 'unknown')),'step':str(job.get('current_step') or ''),'error':str(job.get('last_error') or ''),'updated_at':str(job.get('updated_at') or ''),'recoverable':bool(job.get('recoverable')),'recovery_action':str(job.get('recovery_action') or ''),'source':str(job.get('source') or '')}
            rm.put('project-job-state',slug,state,'timer')
        except Exception:pass
        try:
            rm.invalidate('publication-project-context',slug+'|');rm.invalidate('project-runtime-job',slug)
            ctx=publications._project_context(slug,'');runtime=ctx.get('runtime') or {};status=str(ctx.get('service_status') or 'Não verificado');rm.put('project-runtime-state',slug,{'label':str(runtime.get('versions') or 'Não identificado'),'service':'web','status':status,'healthy':('saudável' in status.lower() or status.lower() in {'running','healthy'})},'timer')
        except Exception:pass
    try:
        base=os.environ.get('CLOUDIF_ONBOARDING_URL','http://127.0.0.1:18208');token=os.environ.get('CLOUDIF_ONBOARDING_API_TOKEN','');rm.put('connectors','all',identities.fetch(base,token),'timer')
    except Exception as exc:print('WARN: connectors readmodel',type(exc).__name__)
    try:
        base=os.environ.get('CLOUDIF_APPROVAL_URL','http://127.0.0.1:18204');token=os.environ.get('CLOUDIF_APPROVAL_TOKEN','');code,data=approvals.request(base,token,'GET','/v1/approvals?status=all');cache_approval_rows(rm,code,data);code,data=approvals.request(base,token,'GET','/v1/approval-policies?status=active');rm.put('approvals','policies',(data.get('policies') or []) if code==200 and isinstance(data,dict) and data.get('ok') else [],'timer')
    except Exception as exc:print('WARN: approvals readmodel',type(exc).__name__)
    try:
        rm.record_event('background-refresh','',['projects','tenants','project-job-state','project-runtime-state','publication-project-context','connectors','approvals'])
    except Exception:pass

def main():
    LIFECYCLE_LOCK.parent.mkdir(parents=True,exist_ok=True);fd=os.open(LIFECYCLE_LOCK,os.O_CREAT|os.O_RDWR,0o600)
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            print("DEFERRED: lifecycle de publicação ativo",now_iso());return
        init_db();refresh_tenants();refresh_nodes();refresh_portal_readmodels();print("OK: cache atualizado",now_iso())
    finally:
        try:fcntl.flock(fd,fcntl.LOCK_UN)
        finally:os.close(fd)

if __name__ == "__main__":
    main()
