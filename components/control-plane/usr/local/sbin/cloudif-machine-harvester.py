#!/usr/bin/env python3
import base64, datetime as dt, hashlib, json, os, platform, re, socket, ssl, subprocess, time, urllib.request
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

STATE=Path('/var/lib/cloudif-machine-agent'); KEY=STATE/'machine-ed25519.key'; MID=STATE/'machine-id'; LAST=STATE/'last-inventory.json'
CONTROLLER=os.environ.get('CLOUDIF_MACHINE_CONTROLLER_URL','http://127.0.0.1:18110').rstrip('/')
AGENT_CA=os.environ.get('CLOUDIF_MACHINE_AGENT_CA','')
AGENT_CERT=os.environ.get('CLOUDIF_MACHINE_AGENT_CERT','')
AGENT_KEY=os.environ.get('CLOUDIF_MACHINE_AGENT_KEY','')
CONFIGURED_MACHINE_ID=os.environ.get('CLOUDIF_MACHINE_ID','').strip()
POLICY_PUBLIC_KEY=os.environ.get('CLOUDIF_MACHINE_POLICY_PUBLIC_KEY','').strip()
POLICY_KEY_ID=os.environ.get('CLOUDIF_MACHINE_POLICY_KEY_ID','').strip()
CERT_CONFIG=Path('/etc/cloudif/certificate-monitoring.json'); CURRENT=STATE/'current-inventory.json'

def verify_policy_envelope(envelope, expected_machine_id, expected_version):
    if not isinstance(envelope,dict): raise ValueError('policy_envelope_invalid')
    payload=envelope.get('payload'); signature=envelope.get('signature_b64'); key_id=str(envelope.get('key_id') or '')
    if not isinstance(payload,dict) or not signature or not key_id: raise ValueError('policy_envelope_incomplete')
    if not POLICY_PUBLIC_KEY or not POLICY_KEY_ID: raise ValueError('policy_trust_not_configured')
    pub_raw=base64.b64decode(Path(POLICY_PUBLIC_KEY).read_text().strip())
    actual_key_id=hashlib.sha256(pub_raw).hexdigest()
    if key_id != POLICY_KEY_ID or actual_key_id != POLICY_KEY_ID: raise ValueError('policy_key_id_mismatch')
    raw=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    Ed25519PublicKey.from_public_bytes(pub_raw).verify(base64.b64decode(signature),raw)
    if str(payload.get('machine_id') or '') != str(expected_machine_id): raise ValueError('policy_machine_id_mismatch')
    if int(payload.get('version') or 0) != int(expected_version): raise ValueError('policy_version_mismatch')
    if payload.get('executor_actions_enabled') is not False: raise ValueError('executor_actions_must_remain_disabled')
    if payload.get('auto_recovery_enabled') is not False: raise ValueError('auto_recovery_must_remain_disabled')
    return payload

def controller_open(target,timeout=60):
    if CONTROLLER.startswith('https://'):
        if not (AGENT_CA and AGENT_CERT and AGENT_KEY): raise RuntimeError('mtls_files_not_configured')
        ctx=ssl.create_default_context(cafile=AGENT_CA)
        ctx.load_cert_chain(certfile=AGENT_CERT,keyfile=AGENT_KEY)
        return urllib.request.urlopen(target,timeout=timeout,context=ctx)
    return urllib.request.urlopen(target,timeout=timeout)

def run(cmd,timeout=20):
    try:
        p=subprocess.run(cmd,text=True,capture_output=True,timeout=timeout); return p.returncode,p.stdout,p.stderr
    except Exception as e: return 99,'',type(e).__name__
def ensure_identity():
    STATE.mkdir(parents=True,exist_ok=True); os.chmod(STATE,0o700)
    if not KEY.exists():
        k=Ed25519PrivateKey.generate(); KEY.write_bytes(k.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption())); os.chmod(KEY,0o600)
    if not MID.exists():
        import uuid
        MID.write_text(CONFIGURED_MACHINE_ID or str(uuid.uuid4())); os.chmod(MID,0o600)
    current=MID.read_text().strip()
    if CONFIGURED_MACHINE_ID and current != CONFIGURED_MACHINE_ID: raise RuntimeError('configured_machine_id_mismatch')
    return Ed25519PrivateKey.from_private_bytes(KEY.read_bytes()),current
def cert_state(days, cfg):
    if days < 0: return 'expired'
    if days <= int(cfg.get('urgent_days',7)): return 'urgent'
    if days <= int(cfg.get('critical_days',14)): return 'critical'
    if days <= int(cfg.get('warning_days',30)): return 'warning'
    return 'ok'

def cert_record(cert, cert_id, name, source, cfg):
    now=dt.datetime.now(dt.timezone.utc)
    not_after=cert.not_valid_after_utc
    not_before=cert.not_valid_before_utc
    days=int((not_after-now).total_seconds()//86400)
    sans=[]
    try:
        ext=cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        sans=ext.value.get_values_for_type(x509.DNSName)+[str(x) for x in ext.value.get_values_for_type(x509.IPAddress)]
    except Exception: pass
    subject=cert.subject.rfc4514_string()
    issuer=cert.issuer.rfc4514_string()
    fp=cert.fingerprint(hashes.SHA256()).hex(':')
    state=cert_state(days,cfg)
    detail=f'days={days} expires={not_after.isoformat()} issuer={issuer} subject={subject}'
    return {'id':cert_id,'kind':'certificate','name':name,'state':state,'detail':detail,'source':source,
            'subject':subject,'issuer':issuer,'serial':format(cert.serial_number,'X'),'not_before':not_before.isoformat(),
            'not_after':not_after.isoformat(),'days_remaining':days,'fingerprint_sha256':fp,'sans':sans}

def load_cert_config():
    try: return json.loads(CERT_CONFIG.read_text())
    except Exception: return {'remote_endpoints':[],'local_paths':[],'warning_days':30,'critical_days':14,'urgent_days':7,'max_local_files':80}

def remote_certificates(cfg):
    out=[]
    for item in cfg.get('remote_endpoints',[]):
        host=str(item.get('host') or ''); port=int(item.get('port') or 443); name=str(item.get('name') or host); server_name=str(item.get('server_name') or host)
        if not host: continue
        cid=f'certificate:remote:{server_name}:{host}:{port}'
        try:
            ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
            with socket.create_connection((host,port),timeout=8) as raw:
                with ctx.wrap_socket(raw,server_hostname=server_name) as tls:
                    der=tls.getpeercert(binary_form=True)
            cert=x509.load_der_x509_certificate(der)
            display_source=f'{server_name} ({host}):{port}' if server_name!=host else f'{host}:{port}'
            out.append(cert_record(cert,cid,name,display_source,cfg))
        except Exception as exc:
            display_source=f'{server_name} ({host}):{port}' if server_name!=host else f'{host}:{port}'
            out.append({'id':cid,'kind':'certificate','name':name,'state':'error','detail':f'{display_source} error={type(exc).__name__}','source':display_source,'days_remaining':None})
    return out

def local_certificates(cfg):
    out=[]; seen=set(); count=0; limit=int(cfg.get('max_local_files',80))
    for root in cfg.get('local_paths',[]):
        p=Path(root)
        if not p.exists(): continue
        paths=[p] if p.is_file() else p.rglob('*')
        for f in paths:
            if count>=limit: return out
            try:
                if not f.is_file() or f.suffix.lower() not in {'.pem','.crt','.cer'}: continue
                if any(x in f.name.lower() for x in ('key','privkey')): continue
                data=f.read_bytes()
                marker=b'-----BEGIN CERTIFICATE-----'
                if marker not in data: continue
                block=marker+data.split(marker,1)[1]
                end=b'-----END CERTIFICATE-----'
                block=block.split(end,1)[0]+end+b'\n'
                cert=x509.load_pem_x509_certificate(block)
                fp=cert.fingerprint(hashes.SHA256()).hex()
                if fp in seen: continue
                seen.add(fp); count+=1
                out.append(cert_record(cert,'certificate:local:'+str(f),f.name,str(f),cfg))
            except Exception: continue
    return out

def certificates():
    cfg=load_cert_config()
    return remote_certificates(cfg)+local_certificates(cfg)

def components():
    out=[]
    rc,txt,_=run(['systemctl','list-units','--type=service','--all','--no-legend','--no-pager'],30)
    for line in txt.splitlines():
        parts=line.split(None,4)
        if len(parts)>=4:
            name,load,active,sub=parts[:4]
            if active in {'active','failed'}: out.append({'id':'systemd:'+name,'kind':'systemd','name':name,'state':active+'/'+sub,'detail':parts[4] if len(parts)>4 else ''})
    rc,txt,_=run(['systemctl','list-timers','--all','--no-legend','--no-pager'],30)
    for line in txt.splitlines():
        parts=line.split()
        if parts: out.append({'id':'timer:'+parts[-1],'kind':'timer','name':parts[-1],'state':'configured','detail':' '.join(parts[:5])})
    rc,txt,_=run(['docker','ps','--format','{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}|{{.Label "com.docker.compose.project"}}|{{.Label "com.docker.compose.service"}}'],40)
    for line in txt.splitlines():
        p=line.split('|',5)
        if len(p)>=4: out.append({'id':'docker:'+p[0],'kind':'container','name':p[0],'state':p[2],'detail':f'image={p[1]} ports={p[3]} project={p[4] if len(p)>4 else ""} service={p[5] if len(p)>5 else ""}'})
    rc,txt,_=run(['ss','-lntupH'],20)
    for line in txt.splitlines():
        cols=line.split()
        if len(cols)>=5:
            proto=cols[0]; local=cols[4]; out.append({'id':'socket:'+proto+':'+local,'kind':'socket','name':local,'state':'listening','detail':proto})
    for path in ['/etc/systemd/system','/etc/cron.d','/etc/cron.daily','/srv/cloudif/managed-backups','/var/backups']:
        p=Path(path)
        if p.exists(): out.append({'id':'path:'+path,'kind':'backup_or_config_path','name':path,'state':'present','detail':'directory'})
    out.extend(certificates())
    return out

def inventory(mid):
    st=os.statvfs('/'); disk_total=st.f_blocks*st.f_frsize; disk_free=st.f_bavail*st.f_frsize
    mem={}
    for line in Path('/proc/meminfo').read_text().splitlines():
        k,v=line.split(':',1); mem[k]=v.strip()
    return {'schema':1,'machine_id':mid,'hostname':socket.gethostname(),'timestamp':dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),'os':platform.platform(),'kernel':platform.release(),'resources':{'load':os.getloadavg(),'disk_total':disk_total,'disk_free':disk_free,'mem_total':mem.get('MemTotal'),'mem_available':mem.get('MemAvailable')},'components':components()}
def main():
    key,mid=ensure_identity(); payload=inventory(mid); raw=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode(); sig=key.sign(raw)
    pub=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    env={'payload':payload,'signature_b64':base64.b64encode(sig).decode(),'public_key_b64':base64.b64encode(pub).decode()}
    req=urllib.request.Request(CONTROLLER+'/api/inventory',data=json.dumps(env).encode(),headers={'Content-Type':'application/json'},method='POST')
    last_error=None
    result=None
    for attempt in range(1,7):
        try:
            with controller_open(req,timeout=60) as r:
                result=json.load(r)
            break
        except Exception as exc:
            last_error=exc
            if attempt < 6:
                time.sleep(min(2 ** attempt, 15))
    if result is None:
        raise RuntimeError('controller_unavailable:'+type(last_error).__name__)
    policy_result={}
    try:
        with controller_open(CONTROLLER+'/api/policy?machine_id='+mid,timeout=30) as pr:
            policy_result=json.load(pr)
        if int(policy_result.get('policy_version') or 0)>0:
            version=int(policy_result.get('policy_version') or 0)
            envelope=policy_result.get('policy') or {}
            verified=verify_policy_envelope(envelope,mid,version)
            policy_path=STATE/'policy.json'
            tmp=STATE/'policy.json.new'
            tmp.write_text(json.dumps(envelope,ensure_ascii=False,indent=2)); os.chmod(tmp,0o600); os.replace(tmp,policy_path)
            ack={'machine_id':mid,'policy_version':version,'key_id':envelope.get('key_id')}
            req_ack=urllib.request.Request(CONTROLLER+'/api/policy/applied',data=json.dumps(ack).encode(),headers={'Content-Type':'application/json'},method='POST')
            controller_open(req_ack,timeout=30).read()
            policy_result['verified']=True
    except Exception as exc:
        policy_result={'ok':False,'error':type(exc).__name__}
    CURRENT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)); os.chmod(CURRENT,0o600)
    LAST.write_text(json.dumps({'sent_at':payload['timestamp'],'result':result,'policy':policy_result,'inventory_hash':result.get('inventory_hash')},ensure_ascii=False,indent=2)); os.chmod(LAST,0o600)
    print(json.dumps({'inventory':result,'policy':policy_result},ensure_ascii=False))
if __name__=='__main__': main()
