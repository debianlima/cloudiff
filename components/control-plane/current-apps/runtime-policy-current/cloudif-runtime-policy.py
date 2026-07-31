#!/usr/bin/env python3
import hashlib,json,os,re
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
POLICY=os.environ.get('CLOUDIF_RUNTIME_POLICY','/etc/cloudif/runtime-policy.json')
HOST=os.environ.get('CLOUDIF_RUNTIME_HOST','127.0.0.1');PORT=int(os.environ.get('CLOUDIF_RUNTIME_PORT','18212'))
def load():
 with open(POLICY) as f:return json.load(f)
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def load_node_execution():
 try:return json.load(open('/etc/cloudif/node-execution-policy.json'))
 except Exception:return {'policy_version':'unavailable','default_version':'24','versions':{},'ready_versions':[],'blocked_versions':['20','22','24'],'secrets_exposed':False}
def load_node24_homologation():
 try:return json.load(open('/etc/cloudif/node24-homologation.json'))
 except Exception:return {'ok':False,'status':'unavailable','node_version':'24','scanner_blocked':True,'secrets_exposed':False}
def detect(ev):
 tech=set(ev.get('technologies') or []); compose=ev.get('compose') or {}; static=ev.get('static') or {}; files=set(ev.get('files') or [])
 scores={}; evidence=[]; conflicts=[]
 def hit(name,score,why): scores[name]=max(scores.get(name,0),score);evidence.append(why)
 if static.get('valid') is True: hit('static',0.94,'workspace.static.valid')
 if any('nginx' in str(x).lower() for x in compose.get('images') or []): hit('static',0.96,'compose.image.nginx')
 mapping={'next.config':'nextjs','vite.config':'vite','nuxt.config':'nuxt','angular.json':'angular','svelte.config':'sveltekit','astro.config':'astro'}
 for prefix,fw in mapping.items():
  if any(str(f).startswith(prefix) for f in files):hit(fw,0.98,'file:'+prefix)
 if len([k for k,v in scores.items() if v>=0.9])>1: conflicts=sorted(scores)
 if not scores:return {'framework':None,'confidence':0.0,'conflicts':[],'evidence':evidence,'human_confirmation_required':True,'reason':'insufficient_repository_evidence'}
 fw=max(scores,key=scores.get); p=load(); cfg=p['frameworks'][fw]; pm=None
 for k,v in p['lockfiles'].items():
  if v in files: pm=k; evidence.append('lockfile:'+v); break
 return {'framework':fw,'confidence':scores[fw],'runtime':cfg.get('runtime'),'runtime_version':p['runtimes'].get(cfg.get('runtime'),{}).get('default') if cfg.get('runtime') else None,'package_manager':pm,'output_directory':cfg.get('output'),'port':cfg.get('port'),'conflicts':conflicts,'evidence':sorted(set(evidence)),'human_confirmation_required':bool(conflicts or scores[fw]<0.9)}
def plan(a):
 p=load(); fw=a.get('framework'); rv=str(a.get('runtime_version') or ''); pm=a.get('package_manager')
 if fw not in p['frameworks']:raise ValueError('framework_not_allowed')
 c=p['frameworks'][fw]; runtime=c.get('runtime')
 if runtime and rv not in p['runtimes'][runtime]['versions']:raise ValueError('runtime_version_not_allowed')
 if runtime and pm not in c.get('package_managers',[]):raise ValueError('package_manager_not_allowed')
 x={'version':1,'runtime':{'name':runtime,'version':rv or None},'framework':{'name':fw,'version':'auto'},'package_manager':{'name':pm,'lockfile_required':bool(runtime)},'build':{'install_command':(c.get('install') or {}).get(pm),'build_command':(c.get('build') or {}).get(pm),'output_directory':c.get('output')},'run':{'start_command':(c.get('start') or {}).get(pm),'port':c.get('port')},'health':{'path':'/','timeout_seconds':10},'deployment':{'type':'web','immutable_image':True},'runtime_policy_version':p['policy_version']}
 return {'ok':True,'side_effect_free':True,'plan':x,'build_plan_digest':digest(x),'commands_derived_from_policy':True,'production_effects_enabled':False}
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def sendj(self,n,x):
  b=json.dumps(x,separators=(',',':')).encode();self.send_response(n);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=='/health':return self.sendj(200,{'ok':True,'service':'runtime-policy','policy_version':load()['policy_version'],'secrets_exposed':False})
  if self.path=='/v1/catalog':
   p=load();n=load_node_execution();h=load_node24_homologation();return self.sendj(200,{'ok':True,'read_only':True,'policy_version':p['policy_version'],'runtimes':p['runtimes'],'frameworks':sorted(p['frameworks']),'ports':p['ports'],'limits':p['limits'],'scanners':p['required_scanners'],'node_execution':n,'node24_homologation':h,'node24_build_ready':bool(h.get('ok') and h.get('status')=='ready' and not h.get('scanner_blocked')),'production_effects_enabled':False,'secrets_exposed':False})
  self.sendj(404,{'ok':False,'error':'not_found'})
 def do_POST(self):
  try:
   n=int(self.headers.get('Content-Length','0')); a=json.loads(self.rfile.read(n) or b'{}')
   if self.path=='/v1/detect':return self.sendj(200,{'ok':True,'read_only':True,'detection':detect(a),'policy_version':load()['policy_version'],'secrets_exposed':False})
   if self.path=='/v1/plan':return self.sendj(200,plan(a))
   if self.path=='/v1/validate':
    r=plan(a);return self.sendj(200,{'ok':True,'valid':True,'build_plan_digest':r['build_plan_digest'],'runtime_policy_version':r['plan']['runtime_policy_version'],'commands_derived_from_policy':True,'arbitrary_command_accepted':False,'production_effects_enabled':False})
   self.sendj(404,{'ok':False,'error':'not_found'})
  except ValueError as e:self.sendj(400,{'ok':False,'error':str(e)})
  except Exception:self.sendj(400,{'ok':False,'error':'invalid_request'})
if __name__ == '__main__':
 ThreadingHTTPServer((HOST,PORT),H).serve_forever()
