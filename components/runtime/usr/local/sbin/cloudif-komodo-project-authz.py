#!/usr/bin/env python3
import json, os, subprocess, sys, tempfile, time
from pathlib import Path

STATE=Path('/var/lib/cloudif/komodo-project-authz')

def main():
    payload=json.load(sys.stdin)
    project=str(payload.get('project') or '').strip().lower()
    owner=str(payload.get('owner') or '').strip().lower()
    stack_id=str(payload.get('stack_id') or '').strip()
    stack_ids=[str(x).strip() for x in (payload.get('stack_ids') or []) if str(x).strip()]
    if stack_id and stack_id not in stack_ids: stack_ids.insert(0,stack_id)
    repo_id=str(payload.get('repo_id') or '').strip()
    acl=payload.get('acl') if isinstance(payload.get('acl'),list) else []
    if not project or not owner or not stack_ids or not repo_id:
        print(json.dumps({'ok':False,'error':'missing_identity_or_resource'}));return 2
    desired=[{'type':'user','subject':owner,'level':'Write'}]
    for item in acl:
        typ=str(item.get('type') or '').strip().lower();subject=str(item.get('subject') or '').strip()
        if typ in {'user','group'} and subject and not (typ=='user' and subject.lower()==owner):
            desired.append({'type':typ,'subject':subject,'level':'Execute'})
    STATE.mkdir(parents=True,exist_ok=True)
    state_path=STATE/(project+'.json')
    previous=[]
    try: previous=json.loads(state_path.read_text()).get('targets') or []
    except Exception: pass
    data={'project':project,'owner':owner,'stack_id':stack_id,'stack_ids':stack_ids,'repo_id':repo_id,'desired':desired,'previous':previous}
    js=r'''
const p=JSON.parse(process.env.CLOUDIF_AUTHZ_PAYLOAD);
const d=db.getSiblingDB('komodo');
const desired=[];const missing=[];
const hex=v=>v&&v.toString?v.toString():String(v||'');
const esc=s=>s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
for(const item of p.desired){
 let target=null;
 if(item.type==='user'){
  const u=d.User.findOne({username:new RegExp('^'+esc(item.subject)+'$','i')});
  if(!u){missing.push({type:'user',subject:item.subject});continue}
  target={type:'User',id:hex(u._id)};
 }else{
  let g=d.UserGroup.findOne({name:item.subject});
  if(!g){d.UserGroup.insertOne({name:item.subject,everyone:false,users:[]});g=d.UserGroup.findOne({name:item.subject});}
  target={type:'UserGroup',id:hex(g._id)};
 }
 const resources=(p.stack_ids||[]).map(id=>({type:'Stack',id:id}));resources.push({type:'Repo',id:p.repo_id});
 for(const resource of resources){
  d.Permission.updateOne({'user_target.type':target.type,'user_target.id':target.id,'resource_target.type':resource.type,'resource_target.id':resource.id},{$set:{user_target:target,resource_target:resource,level:item.level,specific:['Terminal','Inspect']}},{upsert:true});
  desired.push({user_target:target,resource_target:resource});
 }
}
for(const old of (p.previous||[])){
 const keep=desired.some(x=>x.user_target.type===old.user_target.type&&x.user_target.id===old.user_target.id&&x.resource_target.type===old.resource_target.type&&x.resource_target.id===old.resource_target.id);
 if(!keep)d.Permission.deleteOne({'user_target.type':old.user_target.type,'user_target.id':old.user_target.id,'resource_target.type':old.resource_target.type,'resource_target.id':old.resource_target.id});
}
print('CLOUDIF_AUTHZ_RESULT='+JSON.stringify({ok:true,pending:missing.length>0,desired,missing}));
'''
    with tempfile.NamedTemporaryFile('w',delete=False,prefix='cloudif-komodo-project-authz-',suffix='.js') as f:
        f.write(js);host=f.name
    try:
        subprocess.run(['docker','cp',host,'komodo-mongo-1:/tmp/cloudif-project-authz.js'],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=30)
        cmd=['docker','exec','-e','CLOUDIF_AUTHZ_PAYLOAD='+json.dumps(data,separators=(',',':')),'komodo-mongo-1','sh','-lc','U="$MONGO_INITDB_ROOT_USERNAME"; P="$MONGO_INITDB_ROOT_PASSWORD"; mongosh --quiet --username "$U" --password "$P" --authenticationDatabase admin /tmp/cloudif-project-authz.js']
        out=subprocess.run(cmd,check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=60).stdout
        marker=next((x for x in out.splitlines() if x.startswith('CLOUDIF_AUTHZ_RESULT=')),None)
        if not marker: raise RuntimeError('komodo_authz_result_missing')
        result=json.loads(marker.split('=',1)[1]);result.update({'project':project,'owner':owner,'stack_id':stack_id,'stack_ids':stack_ids,'repo_id':repo_id})
        state_path.write_text(json.dumps({'project':project,'request':data,'targets':result.get('desired') or [],'pending':bool(result.get('pending')),'updated_at':int(time.time())},ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(result,ensure_ascii=False));return 0 if result.get('ok') else 3
    except Exception as exc:
        print(json.dumps({'ok':False,'error':'komodo_authz_sync_failed','detail':str(exc)[:500],'project':project},ensure_ascii=False));return 4
    finally:
        try: os.unlink(host)
        except Exception: pass
        subprocess.run(['docker','exec','komodo-mongo-1','rm','-f','/tmp/cloudif-project-authz.js'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
if __name__=='__main__': raise SystemExit(main())
