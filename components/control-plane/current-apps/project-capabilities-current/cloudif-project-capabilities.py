#!/usr/bin/env python3
import ast,datetime,json,os,sqlite3,tempfile
MCP='/srv/cloudif/app-pointers/mcp-gateway-current/cloudif-mcp-gateway.py'
REG='/srv/cloudif/app-pointers/agent-registry-current/cloudif-agent-registry.py'
ON='/var/lib/cloudif/onboarding/onboarding.db'
OUT='/var/lib/cloudif/health/project-capabilities-v2.json'
POL='/etc/cloudif/project-capabilities-policy.json'
TEST_ONLY={'supabase.migrations.plan','deployment.promote-test.plan','approval.request-promote-test','deployment.promote-test','deployment.promote-test.status','deployment.rollback-test.plan','approval.request-rollback-test','deployment.rollback-test'}
CONNECTOR={
 'workspace.':'workspace','forgejo.':'forgejo','supabase.':'supabase',
}
def assigned(tree,name):
 for n in ast.walk(tree):
  if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id==name for x in n.targets):
   return ast.literal_eval(n.value)
 raise KeyError(name)
def load_catalog():
 mt=ast.parse(open(MCP).read());rt=ast.parse(open(REG).read())
 tools=assigned(mt,'TOOLS');scope=assigned(mt,'SCOPE_BY_TOOL');admin=assigned(rt,'PROJECT_ADMIN_SCOPES')
 return tools,scope,admin
def connector_for(name):
 for p,c in CONNECTOR.items():
  if name.startswith(p):return c
 return ''
def classify(name,scope,scopes,connectors,role='project-admin',environment='project'):
 required=scope.get(name,'project:read' if name.startswith('project.') else '')
 authorized=(not required) or required in scopes
 conn=connector_for(name);cstate=(connectors.get(conn) or {}).get('status') if conn else ''
 if name in TEST_ONLY and (role!='test-operator' or environment!='isolated-test'):
  return {'status':'restricted_environment','reason':'exclusive_to_test_operator_isolated_test','required_scope':required,'connector':conn,'connector_status':cstate}
 if not authorized:
  return {'status':'blocked_policy','reason':'scope_not_granted','required_scope':required,'connector':conn,'connector_status':cstate}
 if conn and cstate not in ('ready',''):
  return {'status':'conditional_connector','reason':'connector_'+str(cstate or 'unavailable'),'required_scope':required,'connector':conn,'connector_status':cstate}
 if name.startswith('deployment.production.'):
  return {'status':'enabled_fail_closed','reason':'readiness_and_plan_only','required_scope':required,'connector':conn,'connector_status':cstate}
 return {'status':'enabled','reason':'authorized','required_scope':required,'connector':conn,'connector_status':cstate}
def atomic(path,data,mode=0o600):
 os.makedirs(os.path.dirname(path),exist_ok=True);fd,tmp=tempfile.mkstemp(prefix='.cap-',dir=os.path.dirname(path))
 try:
  with os.fdopen(fd,'w') as f:json.dump(data,f,ensure_ascii=False,separators=(',',':'));f.write('\n');f.flush();os.fsync(f.fileno())
  os.chmod(tmp,mode);os.replace(tmp,path)
 finally:
  try:os.unlink(tmp)
  except FileNotFoundError:pass
def main():
 tools,scope,admin=load_catalog();names=[x['name'] for x in tools]
 c=sqlite3.connect('file:'+ON+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;rows=list(c.execute('select project_slug,client_id,role_profile,environment,status,scopes_json,connectors_json from project_onboarding order by project_slug'));c.close()
 projects=[]
 for r in rows:
  scopes=json.loads(r['scopes_json']);connectors=json.loads(r['connectors_json']);matrix=[]
  for name in names:
   item=classify(name,scope,scopes,connectors,r['role_profile'],r['environment']);item['name']=name;matrix.append(item)
  counts={}
  for x in matrix:counts[x['status']]=counts.get(x['status'],0)+1
  projects.append({'project_slug':r['project_slug'],'client_id':r['client_id'],'role_profile':r['role_profile'],'environment':r['environment'],'onboarding_status':r['status'],'scope_match':scopes==admin,'tool_count':len(matrix),'counts':counts,'tools':matrix})
 future_connectors={'workspace':{'status':'ready'},'forgejo':{'status':'ready'},'mcp':{'status':'ready'},'supabase':{'status':'planned'},'komodo':{'status':'planned'}}
 future=[dict(name=n,**classify(n,scope,admin,future_connectors,'project-admin','project')) for n in names]
 out={'ok':len(projects)>0 and all(p['scope_match'] and p['tool_count']==len(names) for p in projects),'generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'catalog_tools':len(names),'safe_project_admin_tools':sum(1 for x in future if x['status'] in ('enabled','enabled_fail_closed','conditional_connector')),'test_only_tools':sum(1 for x in future if x['status']=='restricted_environment'),'projects':projects,'future_project_template':{'role_profile':'project-admin','environment':'project','tool_count':len(future),'tools':future},'apply_to_existing':True,'apply_to_new':True,'effects_executed':False,'secrets_exposed':False}
 policy={'version':'92A','catalog_tools':len(names),'default_role_profile':'project-admin','default_environment':'project','environment':'project','scope_source':'Agent Registry ROLE_SCOPES','safe_scopes':admin,'test_only_tools':sorted(TEST_ONLY),'apply_to_existing':True,'apply_to_new':True,'reconcile_after_onboarding':True,'reconcile_service':'cloudif-project-onboarding-reconcile.service','capabilities_service':'cloudif-project-capabilities.service','production_effect_scopes_enabled':False,'production_effects_enabled':False}
 atomic(OUT,out,0o600);atomic(POL,policy,0o640);print(json.dumps({'ok':out['ok'],'projects':len(projects),'tools':len(names),'safe':out['safe_project_admin_tools'],'test_only':out['test_only_tools']},separators=(',',':')))
if __name__=='__main__':main()
