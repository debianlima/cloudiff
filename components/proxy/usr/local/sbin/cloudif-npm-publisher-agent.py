#!/usr/bin/env python3
import json,os,re,subprocess,tempfile,shutil,ssl,time,threading
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
ENV=Path('/etc/cloudif/npm-publisher.env')
STATE=Path('/var/lib/cloudif-npm-publisher/state.json')
CONF=Path('/srv/cloudif/proxy/npm/data/nginx/custom/http.conf')
BEGIN='# CloudIF managed publications BEGIN'
END='# CloudIF managed publications END'
HOST='10.62.91.3'; PORT=18160
CERT_LOCK=threading.Lock()

def env():
 d={}
 for line in ENV.read_text().splitlines():
  if '=' in line:
   k,v=line.split('=',1); d[k]=v
 return d

def load_state():
 if not STATE.exists(): return {'projects':{}}
 return json.loads(STATE.read_text())

def save_state(s):
 tmp=STATE.with_suffix('.tmp'); tmp.write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n'); os.chmod(tmp,0o600); tmp.replace(STATE)

def run(cmd,timeout=180):
 p=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
 if p.returncode: raise RuntimeError(f"command_failed:{cmd[0]}:{p.stderr[-500:]}")
 return p.stdout

def cert_exists(name):
 return subprocess.run(['docker','exec','cloudif-nginx-proxy-manager','test','-f',f'/etc/letsencrypt/live/{name}/fullchain.pem']).returncode==0

def cert_covers(name, domains):
 path=f'/srv/cloudif/proxy/npm/letsencrypt/live/{name}/fullchain.pem'
 if not Path(path).exists(): return False
 p=subprocess.run(['openssl','x509','-in',path,'-noout','-ext','subjectAltName'],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if p.returncode: return False
 out=p.stdout.lower()
 return all(('dns:'+d.lower()) in out for d in domains)

def ensure_cert(name,domains):
 domains=sorted(set(str(d).strip().lower() for d in domains if d))
 with CERT_LOCK:
  if cert_exists(name) and cert_covers(name,domains): return name
  cmd=['docker','exec','cloudif-nginx-proxy-manager','certbot','certonly','--webroot','-w','/data/letsencrypt-acme-challenge','--cert-name',name]
  for d in domains: cmd += ['-d',d]
  cmd += ['--non-interactive','--agree-tos','--register-unsafely-without-email','--keep-until-expiring']
  if cert_exists(name): cmd += ['--force-renewal']
  run(cmd,timeout=300)
  if not cert_covers(name,domains): raise RuntimeError('certificate_san_mismatch:'+name)
  return name

def render(state):
 blocks=[]
 for tenant,v in sorted(state.get('tenants',{}).items()):
  if tenant == 'aluno':
   continue
  host=f'{tenant}.cloudiff.duckdns.org'; cert=v['cert']
  blocks.append(f'''server {{
    listen 80;
    listen [::]:80;
    server_name {host};
    location ^~ /.well-known/acme-challenge/ {{ root /data/letsencrypt-acme-challenge; default_type text/plain; }}
    location / {{ return 301 https://$host$request_uri; }}
}}
server {{
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name {host};
    ssl_certificate /etc/letsencrypt/live/{cert}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{cert}/privkey.pem;
    include conf.d/include/ssl-ciphers.conf;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    location / {{
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_pass http://10.62.92.7:8099;
    }}
}}''')
 for num_s,p in sorted(state.get('projects',{}).items(),key=lambda x:int(x[0])):
  num=int(num_s); active=int(p['active_deploy']); stable=f'{num}.cloudiff.duckdns.org'; scert=p['stable_cert']
  blocks.append(f'''server {{\n    listen 80;\n    listen [::]:80;\n    server_name {stable};\n    location ^~ /.well-known/acme-challenge/ {{ root /data/letsencrypt-acme-challenge; default_type text/plain; }}\n    location / {{ return 301 https://$host$request_uri; }}\n}}\nserver {{\n    listen 443 ssl;\n    listen [::]:443 ssl;\n    http2 on;\n    server_name {stable};\n    ssl_certificate /etc/letsencrypt/live/{scert}/fullchain.pem;\n    ssl_certificate_key /etc/letsencrypt/live/{scert}/privkey.pem;\n    include conf.d/include/ssl-ciphers.conf;\n    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;\n    add_header X-Content-Type-Options nosniff always;\n    add_header X-Frame-Options SAMEORIGIN always;\n    location / {{\n        proxy_http_version 1.1;\n        proxy_set_header Host $host;\n        proxy_set_header X-Real-IP $remote_addr;\n        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n        proxy_set_header X-Forwarded-Proto https;\n        proxy_set_header X-Forwarded-Host $host;\n        proxy_set_header Upgrade $http_upgrade;\n        proxy_set_header Connection "upgrade";\n        proxy_pass http://10.62.91.2:18150;\n    }}\n}}''')
  for dep_s,v in sorted(p.get('versions',{}).items(),key=lambda x:int(x[0])):
   dep=int(dep_s); host=f'{num}-d{dep}.cloudiff.duckdns.org'; cert=v['cert']
   blocks.append(f'''server {{\n    listen 80;\n    listen [::]:80;\n    server_name {host};\n    location ^~ /.well-known/acme-challenge/ {{ root /data/letsencrypt-acme-challenge; default_type text/plain; }}\n    location / {{ return 301 https://$host$request_uri; }}\n}}\nserver {{\n    listen 443 ssl;\n    listen [::]:443 ssl;\n    http2 on;\n    server_name {host};\n    ssl_certificate /etc/letsencrypt/live/{cert}/fullchain.pem;\n    ssl_certificate_key /etc/letsencrypt/live/{cert}/privkey.pem;\n    include conf.d/include/ssl-ciphers.conf;\n    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;\n    add_header X-Content-Type-Options nosniff always;\n    add_header X-Frame-Options SAMEORIGIN always;\n    location / {{\n        proxy_http_version 1.1;\n        proxy_set_header Host $host;\n        proxy_set_header X-Real-IP $remote_addr;\n        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n        proxy_set_header X-Forwarded-Proto https;\n        proxy_set_header X-Forwarded-Host $host;\n        proxy_set_header Upgrade $http_upgrade;\n        proxy_set_header Connection "upgrade";\n        proxy_pass http://10.62.91.2:18150;\n    }}\n}}''')
 block=BEGIN+'\n'+'\n\n'.join(blocks)+'\n'+END
 old=CONF.read_text(); backup=CONF.with_name(CONF.name+'.bkp-publisher-'+time.strftime('%Y%m%d-%H%M%S')); shutil.copy2(CONF,backup)
 if BEGIN in old and END in old:
  new=re.sub(re.escape(BEGIN)+r'.*?'+re.escape(END),block,old,flags=re.S)
 else: new=old.rstrip()+'\n\n'+block+'\n'
 CONF.write_text(new)
 try:
  run(['docker','exec','cloudif-nginx-proxy-manager','nginx','-t'],timeout=30)
  run(['docker','exec','cloudif-nginx-proxy-manager','nginx','-s','reload'],timeout=30)
 except Exception:
  shutil.copy2(backup,CONF)
  subprocess.run(['docker','exec','cloudif-nginx-proxy-manager','nginx','-s','reload'])
  raise

def publish(payload):
 num=int(payload.get('public_number')); dep=int(payload.get('deploy_number'))
 if not (1 <= num <= 999999999 and 1 <= dep <= 999999): raise ValueError('invalid_number')
 stable=f'{num}.cloudiff.duckdns.org'; version=f'{num}-d{dep}.cloudiff.duckdns.org'
 state=load_state(); p=state.setdefault('projects',{}).setdefault(str(num),{'active_deploy':dep,'versions':{}})
 # Reuse the combined pilot certificate when present, otherwise use separate certificates.
 if num==1006 and cert_exists('cloudif-p1006'):
  stable_cert='cloudif-p1006'
  if dep == 1:
   version_cert='cloudif-p1006'
  else:
   existing_v = p.get('versions',{}).get(str(dep),{}).get('cert')
   if existing_v == 'cloudif-p1006': existing_v = ''
   version_cert=existing_v or ensure_cert(f'cloudif-p{num}-d{dep}',[version])
 else:
  stable_cert=p.get('stable_cert') or ensure_cert(f'cloudif-p{num}',[stable])
  version_cert=p.get('versions',{}).get(str(dep),{}).get('cert') or ensure_cert(f'cloudif-p{num}-d{dep}',[version])
 p['stable_cert']=stable_cert; p['active_deploy']=dep; p.setdefault('versions',{})[str(dep)]={'cert':version_cert,'created_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 render(state); save_state(state)
 return {'ok':True,'public_number':num,'deploy_number':dep,'stable_url':'https://'+stable+'/','version_url':'https://'+version+'/'}

def ensure_tenant(payload):
 tenant=str(payload.get('tenant') or '').strip().lower()
 if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',tenant): raise ValueError('invalid_tenant')
 host=f'{tenant}.cloudiff.duckdns.org'; cert=ensure_cert(f'cloudif-tenant-{tenant}',[host])
 state=load_state(); state.setdefault('tenants',{})[tenant]={'cert':cert,'updated_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 render(state); save_state(state)
 return {'ok':True,'tenant':tenant,'hostname':host,'url':'https://'+host+'/','certificate':cert}

class H(BaseHTTPRequestHandler):
 def _json(self,code,obj):
  raw=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(code); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
 def _auth(self):
  import hmac
  return hmac.compare_digest(self.headers.get('X-CloudIF-Token',''),env().get('NPM_PUBLISHER_TOKEN',''))
 def do_GET(self):
  if self.path=='/health': return self._json(200,{'ok':True,'service':'cloudif-npm-publisher'})
  return self._json(404,{'ok':False,'error':'not_found'})
 def do_POST(self):
  if not self._auth(): return self._json(403,{'ok':False,'error':'forbidden'})
  try:
   n=int(self.headers.get('Content-Length','0')); payload=json.loads(self.rfile.read(n) or b'{}')
   if self.path=='/publish': return self._json(200,publish(payload))
   if self.path=='/tenant': return self._json(200,ensure_tenant(payload))
   return self._json(404,{'ok':False,'error':'not_found'})
  except Exception as e: return self._json(422,{'ok':False,'error':type(e).__name__,'detail':str(e)[:500]})
 def log_message(self,fmt,*args): pass
if __name__=='__main__': ThreadingHTTPServer((HOST,PORT),H).serve_forever()
