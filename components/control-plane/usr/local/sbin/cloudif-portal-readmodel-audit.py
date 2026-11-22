#!/usr/bin/env python3
import datetime,fcntl,json,os,sqlite3,subprocess,sys,time
from pathlib import Path

PORTAL_DB=Path(os.environ.get('CLOUDIF_PORTAL_DB','/var/lib/cloudif/portal/cloudif-portal.db'))
LOCK=Path('/run/cloudif/portal-readmodel-nightly-audit.lock')

def iso_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')

def portal_con():
    con=sqlite3.connect(PORTAL_DB,timeout=30);con.row_factory=sqlite3.Row;con.execute('pragma busy_timeout=30000');return con

def public_projects(con):
    try:return [dict(r) for r in con.execute('select project_slug,public_number from project_public_ids order by public_number')]
    except Exception:return []

def operational_projects(con):
    slugs=set()
    for table,column in [('project_integrations','project'),('project_preview_source_links','project_slug'),('production_releases','project_slug'),('publication_candidates','project_slug')]:
        try:slugs.update(str(r[0]) for r in con.execute(f'select distinct {column} from {table}') if r[0])
        except Exception:pass
    return slugs

def cache_catalog(rm):
    value=rm.get_stale('projects','public-catalog',7*86400)
    return value if isinstance(value,list) else []

def main():
    LOCK.parent.mkdir(parents=True,exist_ok=True);fd=os.open(LOCK,os.O_CREAT|os.O_RDWR,0o600)
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            print('AUDIT_DEFERRED: already running');return 0
        started=iso_now()
        for lib in ('/srv/cloudif/app-pointers/portal-current','/srv/cloudif/lib'):
            if lib not in sys.path:sys.path.insert(0,lib)
        import cloudif_portal_readmodel as rm
        try:
            subprocess.run(['/usr/bin/systemctl','start','cloudif-portal-refresh-cache.service'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=240,check=False)
        except Exception:pass
        con=portal_con();projects=public_projects(con);operational=operational_projects(con);issues=[]
        db_slugs={str(x.get('project_slug') or '') for x in projects}
        cached=cache_catalog(rm);cache_slugs={str(x.get('slug') or '') for x in cached}
        missing=sorted(db_slugs-cache_slugs);extra=sorted(cache_slugs-db_slugs)
        if missing:issues.append({'code':'catalog-missing-projects','projects':missing})
        if extra:issues.append({'code':'catalog-extra-projects','projects':extra})
        try:
            for r in con.execute("select project_slug,count(*) n from production_releases where status='published' and is_active=1 group by project_slug having count(*)>1"):
                issues.append({'code':'multiple-active-productions','project':str(r['project_slug']),'count':int(r['n'])})
        except Exception:pass
        con.close()
        try:import cloudif_portal_publications as publications
        except Exception as exc:
            publications=None;issues.append({'code':'release-flow-import-failed','error':type(exc).__name__})
        user={'username':'nightly-readmodel-audit','groups':['CloudIF-Tenants-Admin','CloudIF-Professor'],'admin':True,'professor':True}
        audited=[]
        if publications:
            for item in projects:
                slug=str(item.get('project_slug') or '')
                if slug not in operational:continue
                entry={'slug':slug,'public_number':int(item.get('public_number') or 0)}
                try:
                    flow=publications.release_flow_status(slug,user);entry['ok']=True
                    preview=flow.get('preview') or {}
                    if preview.get('configured') and preview.get('healthy') is False:issues.append({'code':'preview-unhealthy','project':slug,'stage':preview.get('stageCode')})
                    releases=flow.get('releases') or []
                    for release in releases:
                        state=release.get('runtimeState') or {};active=int(release.get('is_active') or 0)==1;pn=int(release.get('publication_number') or 0)
                        if active and state.get('online') is False:issues.append({'code':'active-production-offline','project':slug,'publication':pn,'runtimeStatus':state.get('runtimeStatus')})
                        if not active and state.get('online') is True:issues.append({'code':'historical-production-online','project':slug,'publication':pn,'runtimeStatus':state.get('runtimeStatus')})
                    entry['release_count']=len(releases);entry['candidate_count']=len(flow.get('candidates') or [])
                except PermissionError:
                    entry['ok']=True;entry['skipped']='not-visible-to-synthetic-auditor'
                except Exception as exc:
                    entry['ok']=False;entry['error']=type(exc).__name__;issues.append({'code':'release-flow-error','project':slug,'error':type(exc).__name__})
                audited.append(entry)
        finished=iso_now();report={'started_at':started,'finished_at':finished,'project_count':len(projects),'operational_project_count':len(operational),'cached_catalog_count':len(cached),'issues':issues,'audited':audited,'runtime_mutations_performed':False,'secrets_included':False}
        status='ok' if not issues else 'issues'
        rcon=rm._con()
        try:
            rcon.execute('insert into portal_readmodel_audit_runs(started_at,finished_at,status,project_count,issue_count,report_json) values(?,?,?,?,?,?)',(started,finished,status,len(projects),len(issues),json.dumps(report,ensure_ascii=False,separators=(',',':'))));rcon.execute('delete from portal_readmodel_audit_runs where id not in (select id from portal_readmodel_audit_runs order by id desc limit 365)');rcon.commit()
        finally:rcon.close()
        rm.put('audit','last-nightly',report,'nightly-audit');rm.record_event('nightly-audit','',['audit'],{'status':status,'issue_count':len(issues),'project_count':len(projects)})
        print(json.dumps({'ok':True,'status':status,'project_count':len(projects),'issue_count':len(issues),'started_at':started,'finished_at':finished},ensure_ascii=False,separators=(',',':')))
        return 0
    finally:
        try:fcntl.flock(fd,fcntl.LOCK_UN)
        finally:os.close(fd)

if __name__=='__main__':raise SystemExit(main())
