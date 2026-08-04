#!/usr/bin/env python3
import json, subprocess, tempfile, os, time
ADMIN_GROUPS={'CloudIF-Tenants-Admin','CloudIF-Professor'}
def run(cmd, **kw):
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, **kw).stdout
code='''
import json
from authentik.core.models import User
out=[]
for u in User.objects.filter(is_active=True).order_by("username"):
    out.append({"username":u.username,"groups":sorted(list(u.ak_groups.values_list("name",flat=True)))})
print("CLOUDIF_JSON="+json.dumps(out,separators=(",",":")))
'''
auth=run(['docker','exec','authentik-server-1','ak','shell','-c',code])
line=next((x for x in auth.splitlines() if x.startswith('CLOUDIF_JSON=')),None)
if not line:
    raise RuntimeError('authentik_membership_unavailable')
users=json.loads(line.split('=',1)[1])
admins=sorted({u['username'] for u in users if set(u.get('groups') or []).intersection(ADMIN_GROUPS)})
group_names=sorted({g for u in users for g in (u.get('groups') or []) if g})
js=f'''
const d=db.getSiblingDB("komodo");
const source={json.dumps(users)};const admins={json.dumps(admins)};const groupNames={json.dumps(group_names)};
const promoted=d.User.updateMany({{"config.type":"Oidc",username:{{$in:admins}}}},{{$set:{{enabled:true,admin:true,super_admin:true,create_server_permissions:true,create_build_permissions:true}}}});
const demoted=d.User.updateMany({{"config.type":"Oidc",username:{{$nin:admins}}}},{{$set:{{enabled:true,admin:false,super_admin:false,create_server_permissions:false,create_build_permissions:false}}}});
for(const name of groupNames){{
 const memberNames=source.filter(u=>(u.groups||[]).includes(name)).map(u=>u.username);
 const memberIds=d.User.find({{username:{{$in:memberNames}}}},{{_id:1}}).toArray().map(x=>x._id.toString());
 d.UserGroup.updateOne({{name:name}},{{$set:{{name:name,everyone:false,users:memberIds}}}},{{upsert:true}});
}}
print("CLOUDIF_RESULT="+JSON.stringify({{ok:true,admins:admins,groups:groupNames.length,promoted:promoted.modifiedCount,demoted:demoted.modifiedCount}}));
'''
with tempfile.NamedTemporaryFile('w',delete=False,prefix='cloudif-komodo-authz-',suffix='.js') as f:
    f.write(js); host_file=f.name
try:
    run(['docker','cp',host_file,'komodo-mongo-1:/tmp/cloudif-komodo-authz-sync.js'])
    out=run(['docker','exec','komodo-mongo-1','sh','-lc','U="$MONGO_INITDB_ROOT_USERNAME"; P="$MONGO_INITDB_ROOT_PASSWORD"; mongosh --quiet --username "$U" --password "$P" --authenticationDatabase admin /tmp/cloudif-komodo-authz-sync.js'])
    marker=next((x for x in out.splitlines() if x.startswith('CLOUDIF_RESULT=')),None)
    if not marker:
        raise RuntimeError('komodo_mongo_result_missing')
    result=json.loads(marker.split('=',1)[1])
finally:
    try: os.unlink(host_file)
    except FileNotFoundError: pass
    subprocess.run(['docker','exec','komodo-mongo-1','rm','-f','/tmp/cloudif-komodo-authz-sync.js'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
project_authz=[]
state_dir='/var/lib/cloudif/komodo-project-authz'
if os.path.isdir(state_dir):
    for name in sorted(os.listdir(state_dir)):
        if not name.endswith('.json'): continue
        try:
            state=json.load(open(os.path.join(state_dir,name)));request=state.get('request') or {}
            if not request: continue
            proc=subprocess.run(['/usr/local/sbin/cloudif-komodo-project-authz.py'],input=json.dumps(request),text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90)
            item=json.loads((proc.stdout or '{}').splitlines()[-1]);project_authz.append({'project':request.get('project'),'ok':item.get('ok'),'pending':item.get('pending',False)})
        except Exception as exc: project_authz.append({'project':name[:-5],'ok':False,'error':type(exc).__name__})
result.update({'source':'authentik','admin_groups':sorted(ADMIN_GROUPS),'project_authz':project_authz,'timestamp':int(time.time()),'secrets_exposed':False})
os.makedirs('/var/lib/cloudif',exist_ok=True)
with open('/var/lib/cloudif/komodo-authz-sync.json','w') as f: json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps(result,ensure_ascii=False))
