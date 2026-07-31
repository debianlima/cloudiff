#!/usr/bin/env python3
import argparse,datetime as dt,getpass,hashlib,json,os,secrets,subprocess,sys,tempfile,uuid
from pathlib import Path
from cloudif_machine_db import connect
PKI=Path('/var/lib/cloudif-agent-pki'); CONF=PKI/'issuing/openssl.cnf'; ISSUED=PKI/'issued'; ROUTER=Path('/srv/cloudif/router/mtls')

def now(): return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def run(cmd,**kw): return subprocess.run(cmd,text=True,capture_output=True,check=True,**kw)
def audit(actor,action,machine_id='',hostname='',serial='',status='ok',detail=None):
 c=connect(); c.execute('insert into agent_pki_events(created_at,actor,action,machine_id,hostname,serial,status,detail_json) values(?,?,?,?,?,?,?,?)',(now(),actor,action,machine_id,hostname,serial,status,json.dumps(detail or {},ensure_ascii=False))); c.commit(); c.close()
def refresh_crls():
 root=PKI/'root'; issuing=PKI/'issuing'
 run(['openssl','ca','-config',str(root/'ca.cnf'),'-gencrl','-out',str(root/'certs/root-ca.crl.pem')])
 run(['openssl','ca','-config',str(CONF),'-gencrl','-out',str(issuing/'certs/issuing-ca.crl.pem')])
 bundle=(issuing/'certs/issuing-ca.crl.pem').read_bytes()+(root/'certs/root-ca.crl.pem').read_bytes()
 (issuing/'certs/ca-chain.crl.pem').write_bytes(bundle); os.chmod(issuing/'certs/ca-chain.crl.pem',0o644)
 ROUTER.mkdir(parents=True,exist_ok=True); (ROUTER/'ca-chain.crl.pem').write_bytes(bundle); os.chmod(ROUTER/'ca-chain.crl.pem',0o644)
 run(['docker','exec','cloudif-tenant-router','nginx','-t']); run(['docker','exec','cloudif-tenant-router','nginx','-s','reload'])
def create_token(args):
 mid=args.machine_id or str(uuid.uuid4()); token=secrets.token_urlsafe(48); tid=str(uuid.uuid4()); created=now(); expires=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(minutes=args.minutes)).replace(microsecond=0).isoformat().replace('+00:00','Z'); h=hashlib.sha256(token.encode()).hexdigest()
 c=connect(); c.execute('insert into agent_enrollment_tokens(token_id,token_hash,hostname,machine_id,created_by,created_at,expires_at,state) values(?,?,?,?,?,?,?,?)',(tid,h,args.hostname,mid,args.actor,created,expires,'issued')); c.commit(); c.close(); audit(args.actor,'enrollment_token_created',mid,args.hostname,status='ok',detail={'token_id':tid,'expires_at':expires})
 print(json.dumps({'token_id':tid,'token':token,'hostname':args.hostname,'machine_id':mid,'expires_at':expires},ensure_ascii=False))
def enroll(args):
 token=args.token or getpass.getpass('Enrollment token: '); h=hashlib.sha256(token.encode()).hexdigest(); c=connect(); row=c.execute("select * from agent_enrollment_tokens where token_hash=? for update",(h,)).fetchone()
 if not row: c.rollback(); c.close(); raise SystemExit('invalid_token')
 if row['state']!='issued' or row['consumed_at']: c.rollback(); c.close(); raise SystemExit('token_already_consumed')
 if str(row['expires_at'])<now(): c.execute("update agent_enrollment_tokens set state='expired' where token_id=?",(row['token_id'],)); c.commit(); c.close(); raise SystemExit('token_expired')
 csr=Path(args.csr); out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
 text=run(['openssl','req','-in',str(csr),'-noout','-subject','-nameopt','RFC2253']).stdout.strip(); expected='CN='+row['machine_id']
 if expected not in text: c.rollback(); c.close(); raise SystemExit('csr_cn_mismatch')
 ext=out/'client.ext'; ext.write_text(f'''[ client_cert ]\nbasicConstraints = critical,CA:false\nkeyUsage = critical,digitalSignature,keyEncipherment\nextendedKeyUsage = clientAuth\nsubjectKeyIdentifier = hash\nauthorityKeyIdentifier = keyid,issuer\nsubjectAltName = URI:urn:cloudif:machine:{row['machine_id']},DNS:{row['hostname']}\n''')
 cert=out/'client.pem'; chain=out/'client-chain.pem'
 run(['openssl','ca','-batch','-config',str(CONF),'-extensions','client_cert','-extfile',str(ext),'-in',str(csr),'-out',str(cert)])
 chain.write_bytes(cert.read_bytes()+(PKI/'issuing/certs/issuing-ca.pem').read_bytes()); os.chmod(cert,0o644); os.chmod(chain,0o644)
 serial=run(['openssl','x509','-in',str(cert),'-noout','-serial']).stdout.strip().split('=',1)[1]
 c.execute("update agent_enrollment_tokens set state='consumed',consumed_at=?,consumed_serial=? where token_id=?",(now(),serial,row['token_id'])); c.commit(); c.close(); audit(args.actor,'certificate_issued',row['machine_id'],row['hostname'],serial,'ok',{'token_id':row['token_id']})
 print(json.dumps({'hostname':row['hostname'],'machine_id':row['machine_id'],'serial':serial,'certificate':str(cert),'chain':str(chain),'ca_chain':str(PKI/'issuing/certs/ca-chain.pem')},ensure_ascii=False))
def issue_csr(machine_id,hostname,csr_path,out_dir,actor,action='certificate_renewed'):
 csr=Path(csr_path); out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
 text=run(['openssl','req','-in',str(csr),'-noout','-subject','-nameopt','RFC2253']).stdout.strip()
 if ('CN='+machine_id) not in text: raise RuntimeError('csr_cn_mismatch')
 run(['openssl','req','-in',str(csr),'-noout','-verify'])
 ext=out/'client.ext'
 ext.write_text('[ client_cert ]\n'
  'basicConstraints = critical,CA:false\n'
  'keyUsage = critical,digitalSignature,keyEncipherment\n'
  'extendedKeyUsage = clientAuth\n'
  'subjectKeyIdentifier = hash\n'
  'authorityKeyIdentifier = keyid,issuer\n'
  f'subjectAltName = URI:urn:cloudif:machine:{machine_id},DNS:{hostname}\n')
 cert=out/'client.pem'; chain=out/'client-chain.pem'
 run(['openssl','ca','-batch','-config',str(CONF),'-extensions','client_cert','-extfile',str(ext),'-in',str(csr),'-out',str(cert)])
 chain.write_bytes(cert.read_bytes()+(PKI/'issuing/certs/issuing-ca.pem').read_bytes()); os.chmod(cert,0o644); os.chmod(chain,0o644)
 serial=run(['openssl','x509','-in',str(cert),'-noout','-serial']).stdout.strip().split('=',1)[1]
 audit(actor,action,machine_id,hostname,serial,'ok')
 return cert,chain,serial

def renew(args):
 cert,chain,serial=issue_csr(args.machine_id,args.hostname,args.csr,args.out,args.actor)
 print(json.dumps({'machine_id':args.machine_id,'hostname':args.hostname,'serial':serial,'certificate':str(cert),'chain':str(chain)},ensure_ascii=False))

def revoke_serial(args):
 serial=args.serial.upper().replace(':','')
 cert=None
 for x in (PKI/'issuing/newcerts').glob('*.pem'):
  try:
   xs=run(['openssl','x509','-in',str(x),'-noout','-serial']).stdout.strip().split('=',1)[1].upper().replace(':','')
   if xs==serial: cert=x; break
  except Exception: pass
 if cert is None: raise RuntimeError('serial_certificate_not_found')
 run(['openssl','ca','-config',str(CONF),'-revoke',str(cert),'-crl_reason',args.reason]); refresh_crls(); audit(args.actor,'certificate_revoked',args.machine_id or '',args.hostname or '',serial,'ok',{'reason':args.reason}); print(json.dumps({'serial':serial,'revoked':True,'crl_refreshed':True}))

def revoke(args):
 cert=Path(args.cert); serial=run(['openssl','x509','-in',str(cert),'-noout','-serial']).stdout.strip().split('=',1)[1]; subject=run(['openssl','x509','-in',str(cert),'-noout','-subject','-nameopt','RFC2253']).stdout.strip(); mid='';
 for part in subject.split(','):
  if part.startswith('CN='): mid=part[3:]
 run(['openssl','ca','-config',str(CONF),'-revoke',str(cert),'-crl_reason',args.reason]); refresh_crls(); audit(args.actor,'certificate_revoked',mid,args.hostname or '',serial,'ok',{'reason':args.reason}); print(json.dumps({'serial':serial,'machine_id':mid,'revoked':True,'crl_refreshed':True}))
def crl(args): refresh_crls(); audit(args.actor,'crl_refreshed',status='ok'); print('crl_refresh=ok')
def list_tokens(args):
 c=connect(); rows=[dict(r) for r in c.execute('select token_id,hostname,machine_id,created_by,created_at,expires_at,consumed_at,consumed_serial,state from agent_enrollment_tokens order by created_at desc limit 200')]; c.close(); print(json.dumps(rows,ensure_ascii=False,indent=2))
def main():
 ap=argparse.ArgumentParser(); sp=ap.add_subparsers(dest='cmd',required=True)
 p=sp.add_parser('create-token'); p.add_argument('--hostname',required=True); p.add_argument('--machine-id'); p.add_argument('--actor',required=True); p.add_argument('--minutes',type=int,default=15,choices=range(5,61)); p.set_defaults(fn=create_token)
 p=sp.add_parser('enroll'); p.add_argument('--csr',required=True); p.add_argument('--out',required=True); p.add_argument('--token'); p.add_argument('--actor',required=True); p.set_defaults(fn=enroll)
 p=sp.add_parser('revoke'); p.add_argument('--cert',required=True); p.add_argument('--actor',required=True); p.add_argument('--hostname'); p.add_argument('--reason',default='cessationOfOperation',choices=['unspecified','keyCompromise','affiliationChanged','superseded','cessationOfOperation']); p.set_defaults(fn=revoke)
 p=sp.add_parser('renew'); p.add_argument('--csr',required=True); p.add_argument('--out',required=True); p.add_argument('--machine-id',required=True); p.add_argument('--hostname',required=True); p.add_argument('--actor',required=True); p.set_defaults(fn=renew)
 p=sp.add_parser('revoke-serial'); p.add_argument('--serial',required=True); p.add_argument('--machine-id'); p.add_argument('--hostname'); p.add_argument('--actor',required=True); p.add_argument('--reason',default='superseded',choices=['unspecified','keyCompromise','affiliationChanged','superseded','cessationOfOperation']); p.set_defaults(fn=revoke_serial)
 p=sp.add_parser('refresh-crl'); p.add_argument('--actor',required=True); p.set_defaults(fn=crl)
 p=sp.add_parser('list-tokens'); p.set_defaults(fn=list_tokens)
 args=ap.parse_args(); args.fn(args)
if __name__=='__main__': main()
