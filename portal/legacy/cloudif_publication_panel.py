import cloudif_portal_publications as _prodpub
import cloudif_ui_publications as _legacy_pub
import html,json,os,sqlite3,time,urllib.request
DB='/var/lib/cloudif/build-broker/builds.sqlite3'
POLICY='/etc/cloudif/runtime-policy.json'
PREVIEW_DB='/var/lib/cloudif/preview-broker/previews.sqlite3'
NODE24='/etc/cloudif/node24-homologation.json'
def node24_status():
 try:
  x=json.load(open(NODE24));return {'ready':bool(x.get('ok') and x.get('status')=='ready' and not x.get('scanner_blocked')),'sbom_components':x.get('sbom_components'),'scanner_counts':x.get('scanner_counts') or {},'node_version':x.get('node_version')}
 except Exception:return {'ready':False,'node_version':'24','sbom_components':0,'scanner_counts':{}}

def data(visible):
 visible=[dict(p) if not isinstance(p,dict) else p for p in visible]
 allowed={str(p.get('slug')) for p in visible if p.get('slug')}
 policy=json.load(open(POLICY))
 rows=[]
 if os.path.exists(DB):
  c=sqlite3.connect('file:'+DB+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
  for r in c.execute('SELECT id,project_slug,ref,framework,plan_digest,status,created_at,updated_at,attempts,result_json,next_attempt_at,dead_reason FROM builds ORDER BY created_at DESC LIMIT 100'):
   if r['project_slug'] not in allowed:continue
   x=dict(r);x['result']=json.loads(x.pop('result_json') or 'null');x['secrets_exposed']=False;rows.append(x)
 preview_by={}
 if os.path.exists(PREVIEW_DB):
  pc=sqlite3.connect('file:'+PREVIEW_DB+'?mode=ro',uri=True);pc.row_factory=sqlite3.Row
  for r in pc.execute("SELECT id,project_slug,status,expires_at,url,result_json FROM previews WHERE status IN ('active','validated') ORDER BY created_at DESC"):
   if r['project_slug'] in allowed and r['project_slug'] not in preview_by:
    x=dict(r);x['result']=json.loads(x.pop('result_json') or 'null');preview_by[r['project_slug']]=x
 by={s:[] for s in allowed}
 for x in rows:by.setdefault(x['project_slug'],[]).append(x)
 projects=[]
 for p in visible:
  slug=p.get('slug'); hist=by.get(slug,[]); current=hist[0] if hist else None
  projects.append({'slug':slug,'name':p.get('name') or slug,'framework_detected':(current or {}).get('framework'),'framework_selected':(current or {}).get('framework'),'runtime_policy_version':policy.get('policy_version'),'runtime_versions':policy.get('runtimes',{}).get('node',{}).get('versions',[]),'build_current':current,'build_history':hist[:10],'preview':({'ready':True,'status':preview_by[slug]['status'],'url':preview_by[slug]['url'],'expires_at':preview_by[slug]['expires_at']} if slug in preview_by else {'ready':False,'status':'not_configured'}),'production':(_prodpub.production_status(slug) if slug==_prodpub.TARGET_SLUG else {'ready':False,'status':'versioned'}),'rollback':{'ready':False,'status':'not_configured'}})
 return {'ok':True,'policy_version':policy.get('policy_version'),'frameworks':sorted(policy.get('frameworks',{})),'projects':projects,'builds':rows,'queue':{'queued':sum(x['status']=='queued' for x in rows),'running':sum(x['status']=='running' for x in rows),'failed':sum(x['status']=='failed' for x in rows),'dead_letter':sum(x['status']=='dead_letter' for x in rows)},'production_effects_enabled':True,'secrets_exposed':False}
def render(visible):
 d=data(visible);cards=[]
 for p in d['projects']:
  controls=_legacy_pub.publication_panel(p['slug'],p.get('framework_detected') or '')
  cards.append(
   '<article class="publication-project card">'
   '<div class="publication-head"><div>'
   f'<h2>{html.escape(p["name"])}</h2><code>{html.escape(p["slug"])}</code>'
   '</div></div>'+controls+'</article>'
  )
 return '<section class="publication-shell publication-projects-clean">'+''.join(cards)+'</section>'
