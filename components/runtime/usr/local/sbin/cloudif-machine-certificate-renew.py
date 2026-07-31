#!/usr/bin/env python3
import argparse,base64,datetime as dt,hashlib,json,os,shutil,ssl,subprocess,tempfile,urllib.request
from pathlib import Path
STATE=Path('/var/lib/cloudif-machine-agent')
PENDING=STATE/'certificate-renewal.json'
ENV=Path('/etc/cloudif/machine-agent.env')

def load_env():
 d={}
 for line in ENV.read_text().splitlines():
  if '=' in line and not line.lstrip().startswith('#'):
   k,v=line.split('=',1); d[k]=v
 return d

def run(cmd,**kw): return subprocess.run(cmd,text=True,capture_output=True,check=True,**kw)
def serial(cert): return run(['openssl','x509','-in',str(cert),'-noout','-serial']).stdout.strip().split('=',1)[1].upper().replace(':','')
def cert_expiring(cert,days): return subprocess.run(['openssl','x509','-checkend',str(days*86400),'-noout','-in',str(cert)],capture_output=True).returncode!=0

def opener(ca,cert,key):
 ctx=ssl.create_default_context(cafile=str(ca)); ctx.load_cert_chain(certfile=str(cert),keyfile=str(key)); return ctx

def post(url,payload,ca,cert,key):
 req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(req,timeout=90,context=opener(ca,cert,key)) as r: return json.loads(r.read())

def ack_pending(env):
 if not PENDING.exists(): return False
 p=json.loads(PENDING.read_text()); base=env['CLOUDIF_MACHINE_CONTROLLER_URL'].rstrip('/')
 result=post(base+'/api/certificate/renew/ack',{'machine_id':env['CLOUDIF_MACHINE_ID'],'renewal_id':p['renewal_id'],'old_serial':p['old_serial'],'new_serial':p['new_serial']},Path(env['CLOUDIF_MACHINE_AGENT_CA']),Path(env['CLOUDIF_MACHINE_AGENT_CERT']),Path(env['CLOUDIF_MACHINE_AGENT_KEY']))
 if not result.get('ok'): raise RuntimeError('renewal_ack_failed')
 PENDING.unlink(); print('pending_ack=completed old_serial_revoked='+p['old_serial']); return True

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--force',action='store_true'); ap.add_argument('--threshold-days',type=int,default=45); args=ap.parse_args()
 env=load_env(); required=['CLOUDIF_MACHINE_CONTROLLER_URL','CLOUDIF_MACHINE_ID','CLOUDIF_MACHINE_AGENT_CA','CLOUDIF_MACHINE_AGENT_CERT','CLOUDIF_MACHINE_AGENT_KEY']
 for k in required:
  if not env.get(k): raise RuntimeError('missing_env:'+k)
 STATE.mkdir(parents=True,exist_ok=True); os.chmod(STATE,0o700)
 if ack_pending(env): return
 cert=Path(env['CLOUDIF_MACHINE_AGENT_CERT']); key=Path(env['CLOUDIF_MACHINE_AGENT_KEY']); ca=Path(env['CLOUDIF_MACHINE_AGENT_CA'])
 if not args.force and not cert_expiring(cert,args.threshold_days):
  print('renewal=not_due days='+str(args.threshold_days)); return
 old_serial=serial(cert); host=os.uname().nodename; base=env['CLOUDIF_MACHINE_CONTROLLER_URL'].rstrip('/')
 with tempfile.TemporaryDirectory(prefix='cloudif-agent-renew-') as td:
  td=Path(td); new_key=td/'client.key'; csr=td/'client.csr'; new_cert=td/'client.pem'; new_ca=td/'ca-chain.pem'
  run(['openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:3072','-out',str(new_key)])
  os.chmod(new_key,0o600)
  run(['openssl','req','-new','-sha256','-key',str(new_key),'-out',str(csr),'-subj',f"/O=IFF CloudIF/OU=Machine Agents/CN={env['CLOUDIF_MACHINE_ID']}"])
  response=post(base+'/api/certificate/renew',{'machine_id':env['CLOUDIF_MACHINE_ID'],'csr_pem':csr.read_text()},ca,cert,key)
  if not response.get('ok'): raise RuntimeError('renewal_issue_failed')
  new_cert.write_text(response['chain_pem']); new_ca.write_text(response['ca_chain_pem']); os.chmod(new_cert,0o644); os.chmod(new_ca,0o644)
  run(['openssl','verify','-purpose','sslclient','-CAfile',str(new_ca),str(new_cert)])
  key_pub=run(['openssl','pkey','-in',str(new_key),'-pubout']).stdout; cert_pub=run(['openssl','x509','-in',str(new_cert),'-pubkey','-noout']).stdout
  if hashlib.sha256(key_pub.encode()).digest()!=hashlib.sha256(cert_pub.encode()).digest(): raise RuntimeError('certificate_key_mismatch')
  new_serial=serial(new_cert)
  # Test the newly issued identity before installation.
  health=urllib.request.urlopen(base+'/health',timeout=30,context=opener(new_ca,new_cert,new_key)).read()
  if not json.loads(health).get('ok'): raise RuntimeError('new_certificate_health_failed')
  stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M%S'); backup=STATE/'certificate-backups'/stamp; backup.mkdir(parents=True,exist_ok=True); os.chmod(backup,0o700)
  shutil.copy2(cert,backup/'client.pem'); shutil.copy2(key,backup/'client.key'); shutil.copy2(ca,backup/'ca-chain.pem')
  tmp_key=key.with_name(key.name+'.new'); tmp_cert=cert.with_name(cert.name+'.new'); tmp_ca=ca.with_name(ca.name+'.new')
  shutil.copy2(new_key,tmp_key); shutil.copy2(new_cert,tmp_cert); shutil.copy2(new_ca,tmp_ca); os.chmod(tmp_key,0o600); os.chmod(tmp_cert,0o644); os.chmod(tmp_ca,0o644)
  os.replace(tmp_key,key); os.replace(tmp_cert,cert); os.replace(tmp_ca,ca)
  pending={'renewal_id':response['renewal_id'],'old_serial':old_serial,'new_serial':new_serial,'installed_at':dt.datetime.now(dt.timezone.utc).isoformat(),'backup':str(backup)}
  PENDING.write_text(json.dumps(pending,indent=2)); os.chmod(PENDING,0o600)
  ack_pending(env)
  print('renewal=completed old_serial='+old_serial+' new_serial='+new_serial)
if __name__=='__main__': main()
