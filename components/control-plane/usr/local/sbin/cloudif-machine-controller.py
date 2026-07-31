#!/usr/bin/env python3
import base64, datetime as dt, hashlib, hmac, html, json, os, secrets, subprocess, sys, tempfile, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cloudif_machine_db import connect as db_connect, init_schema

HOST=os.environ.get('CLOUDIF_MACHINE_CONTROLLER_HOST','127.0.0.1')
PORT=int(os.environ.get('CLOUDIF_MACHINE_CONTROLLER_PORT','18110'))
MAX_BODY=8*1024*1024

def now(): return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def con(): return db_connect()

def init(): init_schema()

def verify(payload, signature_b64, public_key_b64):
    raw=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64)).verify(base64.b64decode(signature_b64),raw)
    return hashlib.sha256(raw).hexdigest()

def process_certificates(c, machine_id, payload, observed_at):
    certs=[x for x in payload.get('components',[]) if x.get('kind')=='certificate' and x.get('id')]
    seen_ids=set()
    for cert in certs:
        cert_id=str(cert.get('id')); seen_ids.add(cert_id)
        fp=str(cert.get('fingerprint_sha256') or '')
        name=str(cert.get('name') or cert_id); source=str(cert.get('source') or '')
        state=str(cert.get('state') or 'error'); days=cert.get('days_remaining')
        previous=c.execute('select fingerprint_sha256,not_after,state from certificate_history where machine_id=? and cert_id=? order by id desc limit 1',(machine_id,cert_id)).fetchone()
        c.execute("""insert into certificate_history(machine_id,cert_id,name,source,fingerprint_sha256,subject,issuer,not_before,not_after,first_seen,last_seen,state,days_remaining)
                     values(?,?,?,?,?,?,?,?,?,?,?,?,?)
                     on conflict(machine_id,cert_id,fingerprint_sha256) do update set last_seen=excluded.last_seen,state=excluded.state,days_remaining=excluded.days_remaining,not_after=excluded.not_after,issuer=excluded.issuer,subject=excluded.subject""",
                  (machine_id,cert_id,name,source,fp,str(cert.get('subject') or ''),str(cert.get('issuer') or ''),str(cert.get('not_before') or ''),str(cert.get('not_after') or ''),observed_at,observed_at,state,days))
        cert_serial_current=normalize_serial(cert.get('serial'))
        planned_current=False
        if cert_serial_current:
            planned_current=bool(c.execute("select 1 from agent_certificate_renewals where machine_id=? and new_serial=? and state='installed' limit 1",(machine_id,cert_serial_current)).fetchone())
            if not planned_current:
                planned_current=bool(c.execute("select 1 from agent_pki_events where action='controller_certificate_rotated' and serial=? and status='ok' limit 1",(cert_serial_current,)).fetchone())
        if planned_current:
            c.execute("update certificate_alerts set state='resolved',resolved_at=?,updated_at=?,message=? where machine_id=? and cert_id=? and state='open' and alert_key like ?",(observed_at,observed_at,f'Renovação planejada confirmada para {name}.',machine_id,cert_id,f'{machine_id}|{cert_id}|fingerprint|%'))
        if previous and fp and previous['fingerprint_sha256'] and previous['fingerprint_sha256']!=fp:
            cert_serial=normalize_serial(cert.get('serial'))
            planned=False
            if cert_serial:
                planned=bool(c.execute("select 1 from agent_certificate_renewals where machine_id=? and new_serial=? and state='installed' limit 1",(machine_id,cert_serial)).fetchone())
                if not planned:
                    planned=bool(c.execute("select 1 from agent_pki_events where action='controller_certificate_rotated' and serial=? and status='ok' limit 1",(cert_serial,)).fetchone())
            if planned:
                c.execute("update certificate_alerts set state='resolved',resolved_at=?,updated_at=?,message=? where machine_id=? and cert_id=? and state='open' and alert_key like ?",(observed_at,observed_at,f'Renovação planejada confirmada para {name}.',machine_id,cert_id,f'{machine_id}|{cert_id}|fingerprint|%'))
            else:
                prev_exp=str(previous['not_after'] or '')
                sev='info' if prev_exp and prev_exp <= observed_at else 'warning'
                key=f'{machine_id}|{cert_id}|fingerprint|{fp}'
                msg=f'Fingerprint alterado para {name}.'
                detail={'name':name,'source':source,'previous_fingerprint':previous['fingerprint_sha256'],'new_fingerprint':fp,'previous_not_after':prev_exp,'new_not_after':cert.get('not_after'),'classification':'renewal' if sev=='info' else 'unexpected_change'}
                c.execute("""insert into certificate_alerts(machine_id,cert_id,alert_key,severity,state,opened_at,updated_at,message,detail_json)
                             values(?,?,?,?,?,?,?,?,?) on conflict(alert_key) do update set updated_at=excluded.updated_at,state='open',message=excluded.message,detail_json=excluded.detail_json""",
                          (machine_id,cert_id,key,sev,'open',observed_at,observed_at,msg,json.dumps(detail,ensure_ascii=False)))
        if state in {'warning','critical','urgent','expired','error'}:
            sev={'warning':'info','critical':'warning','urgent':'high','expired':'high','error':'high'}[state]
            key=f'{machine_id}|{cert_id}|state|{state}'
            msg=f'Certificado {name} em estado {state}.'
            detail={'name':name,'source':source,'days_remaining':days,'not_after':cert.get('not_after'),'fingerprint_sha256':fp}
            c.execute("""insert into certificate_alerts(machine_id,cert_id,alert_key,severity,state,opened_at,updated_at,message,detail_json)
                         values(?,?,?,?,?,?,?,?,?) on conflict(alert_key) do update set updated_at=excluded.updated_at,state='open',resolved_at=null,message=excluded.message,detail_json=excluded.detail_json""",
                      (machine_id,cert_id,key,sev,'open',observed_at,observed_at,msg,json.dumps(detail,ensure_ascii=False)))
        else:
            c.execute("update certificate_alerts set state='resolved',resolved_at=?,updated_at=? where machine_id=? and cert_id=? and state='open' and alert_key like ?",(observed_at,observed_at,machine_id,cert_id,f'{machine_id}|{cert_id}|state|%'))
    rows=c.execute("select distinct cert_id from certificate_alerts where machine_id=? and state='open'",(machine_id,)).fetchall()
    for row in rows:
        if row['cert_id'] not in seen_ids:
            c.execute("update certificate_alerts set state='resolved',resolved_at=?,updated_at=? where machine_id=? and cert_id=? and state='open'",(observed_at,observed_at,machine_id,row['cert_id']))

def upsert_inventory(data):
    payload=data.get('payload'); sig=data.get('signature_b64',''); pub=data.get('public_key_b64','')
    if not isinstance(payload,dict) or not sig or not pub: raise ValueError('invalid_envelope')
    mid=str(payload.get('machine_id') or ''); hostname=str(payload.get('hostname') or '')
    if not mid or not hostname: raise ValueError('invalid_identity')
    c=con(); old=c.execute('select public_key_b64,inventory_hash from machines where machine_id=?',(mid,)).fetchone()
    if old and old['public_key_b64'] != pub: c.close(); raise ValueError('public_key_changed')
    digest=verify(payload,sig,pub)
    changed=not old or old['inventory_hash']!=digest
    state='pending_confirmation' if changed else 'active'
    inv=json.dumps(payload,ensure_ascii=False)
    t=now()
    c.execute('''insert into machines(machine_id,hostname,state,first_seen,last_seen,public_key_b64,inventory_hash,inventory_json,message)
      values(?,?,?,?,?,?,?,?,?) on conflict(machine_id) do update set hostname=excluded.hostname,state=case when machines.policy_version=0 then 'pending_confirmation' when excluded.inventory_hash<>machines.inventory_hash then 'pending_confirmation' else machines.state end,last_seen=excluded.last_seen,inventory_hash=excluded.inventory_hash,inventory_json=excluded.inventory_json,message=excluded.message''',
      (mid,hostname,state,t,t,pub,digest,inv,'Inventário recebido; confirmação administrativa pendente.' if changed else 'Inventário atualizado.'))
    if changed: c.execute('insert into inventory_events(machine_id,created_at,inventory_hash,inventory_json) values(?,?,?,?)',(mid,t,digest,inv))
    process_certificates(c,mid,payload,t)
    c.commit(); row=c.execute('select state,policy_version from machines where machine_id=?',(mid,)).fetchone(); c.close()
    return {'ok':True,'machine_id':mid,'state':row['state'],'policy_version':row['policy_version'],'inventory_hash':digest,'changed':changed}

def _canonical(obj): return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()

def _policy_private_key():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    path=Path(os.environ['CLOUDIF_MACHINE_POLICY_SIGNING_KEY'])
    return Ed25519PrivateKey.from_private_bytes(path.read_bytes())

def sign_policy(policy):
    sig=_policy_private_key().sign(_canonical(policy))
    return {'schema':1,'payload':policy,'signature_b64':base64.b64encode(sig).decode(),'key_id':os.environ['CLOUDIF_MACHINE_POLICY_KEY_ID']}

def confirm_policy(mid, selections):
    c=con(); row=c.execute('select inventory_json,policy_version from machines where machine_id=?',(mid,)).fetchone()
    if not row: c.close(); raise ValueError('machine_not_found')
    inv=json.loads(row['inventory_json']); allowed={x.get('id') for x in inv.get('components',[]) if x.get('id')}
    clean=[]
    for x in selections:
        cid=str(x.get('id') or '')
        if cid not in allowed: continue
        clean.append({'id':cid,'monitor':bool(x.get('monitor')),'guard':bool(x.get('guard')),'auto_recover':False,'backup':bool(x.get('backup'))})
    ver=int(row['policy_version'])+1
    policy={'machine_id':mid,'version':ver,'issued_at':now(),'components':clean,'auto_recovery_enabled':False,'executor_actions_enabled':False}
    envelope=sign_policy(policy)
    c.execute('update machines set state=?,policy_version=?,policy_json=?,message=? where machine_id=?',('policy_issued',ver,json.dumps(envelope,ensure_ascii=False),'Política assinada emitida após aprovação dupla; ações do Executor permanecem bloqueadas.',mid))
    c.commit(); c.close(); return envelope

ROLE_GROUPS={
 'viewer':{'cloudif-tenants','cloudif-professor','cloudif-tenants-admin','cloudif-admin','cloudif-infra-admin','domain admins','enterprise admins'},
 'operator':{'cloudif-professor','cloudif-tenants-admin','cloudif-admin','cloudif-infra-admin','domain admins','enterprise admins'},
 'maintainer':{'cloudif-tenants-admin','cloudif-admin','cloudif-infra-admin','domain admins','enterprise admins'},
 'approver':{'cloudif-tenants-admin','cloudif-infra-admin','domain admins','enterprise admins'},
 'security_admin':{'domain admins','enterprise admins','cloudif-infra-admin'},
}

def header_groups(headers):
    raw=headers.get('X-authentik-groups') or headers.get('X-Authentik-Groups') or ''
    return {x.strip().lower() for x in raw.replace('|',',').split(',') if x.strip()}

def admin_context(headers):
    actor=(headers.get('X-authentik-username') or headers.get('X-Authentik-Username') or headers.get('X-Forwarded-User') or '').strip().lower()
    groups=header_groups(headers); roles={role for role,allowed in ROLE_GROUPS.items() if groups.intersection(allowed)}
    return actor,roles,groups

def admin_identity(headers):
    actor,roles,_=admin_context(headers); return actor,bool(actor and roles)

def remote_agent_identity(headers):
    if (headers.get('X-CloudIF-Agent-Remote') or '') != '1': return None
    if (headers.get('X-SSL-Client-Verify') or '') != 'SUCCESS': raise ValueError('mtls_client_not_verified')
    dn=(headers.get('X-SSL-Client-DN') or '').strip()
    import re
    match=re.search(r'(?:^|,)CN=([^,]+)',dn)
    if not match: raise ValueError('mtls_client_cn_missing')
    return match.group(1).strip()

def require_remote_machine(headers, machine_id):
    remote=remote_agent_identity(headers)
    if remote is not None and remote != str(machine_id or ''): raise ValueError('mtls_machine_id_mismatch')
    return remote

SESSION_COOKIE='cloudif_machine_admin_session'; SESSION_TTL=1800

def _session_secret():
    value=os.environ.get('CLOUDIF_MACHINE_ADMIN_SESSION_SECRET','')
    if len(value)<48: raise RuntimeError('session_secret_not_configured')
    return value.encode()
def _b64u(raw): return base64.urlsafe_b64encode(raw).decode().rstrip('=')
def _unb64u(text): return base64.urlsafe_b64decode(text+'='*((4-len(text)%4)%4))
def issue_session(actor):
    payload={'actor':actor,'exp':int(time.time())+SESSION_TTL,'nonce':secrets.token_urlsafe(18)}
    body=_b64u(_canonical(payload)); sig=_b64u(hmac.new(_session_secret(),body.encode(),hashlib.sha256).digest())
    return body+'.'+sig
def validate_session(token,actor):
    try:
        body,sig=token.split('.',1); expected=_b64u(hmac.new(_session_secret(),body.encode(),hashlib.sha256).digest())
        if not hmac.compare_digest(sig,expected): return False
        payload=json.loads(_unb64u(body)); return payload.get('actor')==actor and int(payload.get('exp',0))>=int(time.time())
    except Exception: return False
def csrf_for(token): return _b64u(hmac.new(_session_secret(),('csrf:'+token).encode(),hashlib.sha256).digest())
def cookie_token(headers):
    raw=headers.get('Cookie') or ''
    for part in raw.split(';'):
        k,sep,v=part.strip().partition('=')
        if sep and k==SESSION_COOKIE:return v
    return ''
def session_cookie(token): return f'{SESSION_COOKIE}={token}; Max-Age={SESSION_TTL}; Path=/; Secure; HttpOnly; SameSite=Strict'

def audit(actor,action,target,status,detail=None,source_ip=''):
    c=con(); c.execute('insert into admin_audit_events(created_at,actor,action,target,status,detail_json,source_ip) values(?,?,?,?,?,?,?)',(now(),actor,action,target,status,json.dumps(detail or {},ensure_ascii=False),source_ip)); c.commit(); c.close()

def create_policy_request(mid, selections, actor, source_ip):
    c=con(); row=c.execute('select machine_id from machines where machine_id=?',(mid,)).fetchone()
    if not row: c.close(); raise ValueError('machine_not_found')
    rid=str(uuid.uuid4()); requested=now(); expires=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=24)).replace(microsecond=0).isoformat().replace('+00:00','Z')
    payload={'components':selections}
    c.execute('insert into admin_requests(request_id,kind,target_machine_id,payload_json,requested_by,requested_at,status,expires_at) values(?,?,?,?,?,?,?,?)',(rid,'policy_confirm',mid,json.dumps(payload,ensure_ascii=False),actor,requested,'pending_approval',expires)); c.commit(); c.close()
    audit(actor,'policy_request',mid,'pending_approval',{'request_id':rid,'component_count':len(selections)},source_ip); return rid

def approve_request(rid,actor,source_ip):
    c=con(); row=c.execute('select * from admin_requests where request_id=?',(rid,)).fetchone()
    if not row: c.close(); raise ValueError('request_not_found')
    if row['status']!='pending_approval': c.close(); raise ValueError('request_not_pending')
    if row['requested_by']==actor: c.close(); raise ValueError('dual_approval_requires_distinct_user')
    if str(row['expires_at'])<now():
        c.execute("update admin_requests set status='expired' where request_id=?",(rid,)); c.commit(); c.close(); raise ValueError('request_expired')
    cur=c.execute("update admin_requests set status='approving',approved_by=?,approved_at=? where request_id=? and status='pending_approval'",(actor,now(),rid))
    if cur.rowcount!=1: c.rollback(); c.close(); raise ValueError('request_concurrent_change')
    c.commit(); c.close()
    try:
        payload=json.loads(row['payload_json'] or '{}')
        if row['kind']!='policy_confirm': raise ValueError('unsupported_request_kind')
        result=confirm_policy(row['target_machine_id'],payload.get('components') or [])
        c=con(); c.execute("update admin_requests set status='executed',executed_at=?,result_json=? where request_id=?",(now(),json.dumps({'policy_version':result['payload']['version'],'key_id':result['key_id']},ensure_ascii=False),rid)); c.commit(); c.close()
        audit(actor,'request_approve',rid,'executed',{'requested_by':row['requested_by'],'machine_id':row['target_machine_id']},source_ip); return result
    except Exception as exc:
        c=con(); c.execute("update admin_requests set status='failed',executed_at=?,result_json=? where request_id=?",(now(),json.dumps({'error':type(exc).__name__,'message':str(exc)[:200]}),rid)); c.commit(); c.close(); audit(actor,'request_approve',rid,'failed',{'error':type(exc).__name__},source_ip); raise

def normalize_serial(value): return str(value or '').upper().replace(':','').strip()

def issue_certificate_renewal(machine_id,old_serial,csr_pem):
    c=con(); row=c.execute('select hostname from machines where machine_id=?',(machine_id,)).fetchone(); c.close()
    if not row: raise ValueError('machine_not_found')
    if not csr_pem or 'BEGIN CERTIFICATE REQUEST' not in csr_pem: raise ValueError('csr_invalid')
    rid=str(uuid.uuid4()); work=Path(tempfile.mkdtemp(prefix='cloudif-cert-renew-'))
    try:
        csr=work/'client.csr'; out=work/'out'; csr.write_text(csr_pem); os.chmod(csr,0o600)
        env=os.environ.copy(); env['PYTHONPATH']='/srv/cloudif/lib'
        cp=subprocess.run(['/usr/local/sbin/cloudif-agent-pki.py','renew','--csr',str(csr),'--out',str(out),'--machine-id',machine_id,'--hostname',row['hostname'],'--actor','system:mtls-renewal'],env=env,text=True,capture_output=True,timeout=90,check=True)
        result=json.loads(cp.stdout.strip().splitlines()[-1]); new_serial=normalize_serial(result['serial'])
        cert=Path(result['certificate']).read_text(); chain=Path(result['chain']).read_text(); ca=Path('/var/lib/cloudif-agent-pki/issuing/certs/ca-chain.pem').read_text()
        c=con(); c.execute('insert into agent_certificate_renewals(renewal_id,machine_id,hostname,old_serial,new_serial,requested_at,state,detail_json) values(?,?,?,?,?,?,?,?)',(rid,machine_id,row['hostname'],normalize_serial(old_serial),new_serial,now(),'issued',json.dumps({'actor':'mtls','csr_sha256':hashlib.sha256(csr_pem.encode()).hexdigest()},ensure_ascii=False))); c.commit(); c.close()
        return {'renewal_id':rid,'machine_id':machine_id,'old_serial':normalize_serial(old_serial),'new_serial':new_serial,'certificate_pem':cert,'chain_pem':chain,'ca_chain_pem':ca}
    finally:
        import shutil as _shutil; _shutil.rmtree(work,ignore_errors=True)

def finalize_certificate_renewal(machine_id,new_serial,old_serial,renewal_id):
    new_serial=normalize_serial(new_serial); old_serial=normalize_serial(old_serial)
    c=con(); row=c.execute("select * from agent_certificate_renewals where renewal_id=? and machine_id=? and new_serial=? and old_serial=? and state='issued'",(renewal_id,machine_id,new_serial,old_serial)).fetchone(); c.close()
    if not row: raise ValueError('renewal_not_pending')
    env=os.environ.copy(); env['PYTHONPATH']='/srv/cloudif/lib'
    subprocess.run(['/usr/local/sbin/cloudif-agent-pki.py','revoke-serial','--serial',old_serial,'--machine-id',machine_id,'--hostname',row['hostname'],'--actor','system:mtls-renewal-ack','--reason','superseded'],env=env,text=True,capture_output=True,timeout=90,check=True)
    c=con(); c.execute("update agent_certificate_renewals set state='installed',installed_at=? where renewal_id=?",(now(),renewal_id)); c.commit(); c.close()
    return {'ok':True,'renewal_id':renewal_id,'old_serial_revoked':old_serial,'new_serial':new_serial}

def acknowledge_alert(alert_id,actor,note,source_ip):
    c=con(); cur=c.execute("update certificate_alerts set acknowledged_by=?,acknowledged_at=?,acknowledgment_note=? where id=? and state='open'",(actor,now(),note[:500],int(alert_id)))
    if cur.rowcount!=1: c.rollback(); c.close(); raise ValueError('alert_not_open')
    c.commit(); c.close(); audit(actor,'certificate_alert_ack',str(alert_id),'ok',{'note':note[:500]},source_ip)

def dashboard(actor,roles,csrf):
    c=con(); machines=[dict(r) for r in c.execute('select machine_id,hostname,state,last_seen,policy_version,message,inventory_json from machines order by hostname')]; alerts=[dict(r) for r in c.execute("select id,severity,state,opened_at,updated_at,message,acknowledged_by,acknowledged_at from certificate_alerts order by case state when 'open' then 0 else 1 end,updated_at desc limit 50")]; history=[dict(r) for r in c.execute("select name,source,fingerprint_sha256,first_seen,last_seen,not_after,state from certificate_history order by last_seen desc,id desc limit 50")]; requests=[dict(r) for r in c.execute("select request_id,kind,target_machine_id,requested_by,requested_at,status,approved_by,approved_at,expires_at from admin_requests order by requested_at desc limit 50")]; c.close()
    cards=[]; all_certs=[]
    for m in machines:
        inv=json.loads(m.pop('inventory_json') or '{}'); comps=inv.get('components',[]); all_certs.extend([dict(x,machine=m['hostname']) for x in comps if x.get('kind')=='certificate'])
        if 'maintainer' in roles:
            rows=''.join(f"<tr><td><input type='checkbox' name='monitor' value='{html.escape(str(x.get('id','')))}'></td><td>{html.escape(str(x.get('kind','')))}</td><td>{html.escape(str(x.get('name','')))}</td><td>{html.escape(str(x.get('state','')))}</td><td>{html.escape(str(x.get('detail','')))}</td></tr>" for x in comps[:250])
            body=f"<form method='post' action='/admin/policy/request'><input type='hidden' name='csrf_token' value='{html.escape(csrf)}'><input type='hidden' name='machine_id' value='{html.escape(m['machine_id'])}'><p><button type='submit'>Solicitar política para os componentes selecionados</button></p><table><thead><tr><th>Monitorar</th><th>Tipo</th><th>Componente</th><th>Estado</th><th>Detalhe</th></tr></thead><tbody>{rows}</tbody></table></form>"
        else:
            rows=''.join(f"<tr><td>{html.escape(str(x.get('kind','')))}</td><td>{html.escape(str(x.get('name','')))}</td><td>{html.escape(str(x.get('state','')))}</td><td>{html.escape(str(x.get('detail','')))}</td></tr>" for x in comps[:250]); body=f"<p><b>Modo:</b> somente leitura</p><table><thead><tr><th>Tipo</th><th>Componente</th><th>Estado</th><th>Detalhe</th></tr></thead><tbody>{rows}</tbody></table>"
        cards.append(f"<section><h2>{html.escape(m['hostname'])}</h2><p><b>Estado:</b> {html.escape(m['state'])} · <b>Último heartbeat:</b> {html.escape(m['last_seen'])} · <b>Política:</b> {m['policy_version']}</p><p>{html.escape(m['message'])}</p>{body}</section>")
    order={'expired':0,'error':1,'urgent':2,'critical':3,'warning':4,'ok':5}; all_certs.sort(key=lambda x:(order.get(x.get('state'),9),x.get('days_remaining') if isinstance(x.get('days_remaining'),int) else 999999,x.get('name','')))
    cert_rows=''.join(f"<tr class='cert-{html.escape(str(x.get('state','')))}'><td>{html.escape(str(x.get('name','')))}</td><td>{html.escape(str(x.get('machine','')))}</td><td>{html.escape(str(x.get('source','')))}</td><td><b>{html.escape(str(x.get('state','')))}</b></td><td>{html.escape(str(x.get('days_remaining','-')))}</td><td>{html.escape(str(x.get('not_after','-')))}</td><td>{html.escape(str(x.get('issuer','-')))}</td></tr>" for x in all_certs)
    counts={k:sum(1 for x in all_certs if x.get('state')==k) for k in ('ok','warning','critical','urgent','expired','error')}
    cert_section=f"<section><h2>Certificados</h2><p><b>Total:</b> {len(all_certs)} · <b>OK:</b> {counts['ok']} · <b>Aviso:</b> {counts['warning']} · <b>Crítico:</b> {counts['critical']} · <b>Urgente:</b> {counts['urgent']} · <b>Expirado:</b> {counts['expired']} · <b>Erro:</b> {counts['error']}</p><table><thead><tr><th>Certificado</th><th>Máquina</th><th>Origem</th><th>Estado</th><th>Dias</th><th>Validade</th><th>Emissor</th></tr></thead><tbody>{cert_rows}</tbody></table></section>"
    alert_rows=[]
    for x in alerts:
        action=''
        if x['state']=='open' and not x.get('acknowledged_by') and 'operator' in roles: action=f"<form method='post' action='/admin/alerts/ack'><input type='hidden' name='csrf_token' value='{html.escape(csrf)}'><input type='hidden' name='alert_id' value='{x['id']}'><input name='note' maxlength='500' placeholder='Observação'><button type='submit'>Reconhecer</button></form>"
        alert_rows.append(f"<tr><td>{html.escape(str(x['severity']))}</td><td>{html.escape(str(x['state']))}</td><td>{html.escape(str(x['message']))}</td><td>{html.escape(str(x.get('acknowledged_by') or '-'))}</td><td>{action}</td></tr>")
    request_rows=[]
    for r in requests:
        action=''
        if r['status']=='pending_approval' and r['requested_by']!=actor and 'approver' in roles: action=f"<form method='post' action='/admin/requests/approve'><input type='hidden' name='csrf_token' value='{html.escape(csrf)}'><input type='hidden' name='request_id' value='{html.escape(r['request_id'])}'><button type='submit'>Aprovar e executar</button></form>"
        request_rows.append(f"<tr><td><code>{html.escape(r['request_id'])}</code></td><td>{html.escape(r['kind'])}</td><td>{html.escape(str(r.get('target_machine_id') or ''))}</td><td>{html.escape(r['requested_by'])}</td><td>{html.escape(r['status'])}</td><td>{html.escape(str(r.get('approved_by') or '-'))}</td><td>{action}</td></tr>")
    hist_rows=''.join(f"<tr><td>{html.escape(str(x.get('name','')))}</td><td>{html.escape(str(x.get('source','')))}</td><td><code>{html.escape(str(x.get('fingerprint_sha256','')))}</code></td><td>{html.escape(str(x.get('first_seen','')))}</td><td>{html.escape(str(x.get('last_seen','')))}</td><td>{html.escape(str(x.get('not_after','')))}</td></tr>" for x in history)
    return ('<!doctype html><html><head><meta charset="utf-8"><title>CloudIF Administração de Máquinas</title><style>body{font-family:system-ui;background:#0f172a;color:#e2e8f0;margin:24px}section{background:#172033;padding:18px;border-radius:12px;margin-bottom:18px}table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:7px;border-bottom:1px solid #334155}th{color:#93c5fd}code{color:#86efac}button{padding:7px 11px}.cert-warning{background:#493b12}.cert-critical{background:#5b350d}.cert-urgent,.cert-expired,.cert-error{background:#5c1d24}.cert-ok{background:#123b2b}</style></head><body><h1>CloudIF · Administração de Máquinas</h1><p>Usuário: '+html.escape(actor)+' · Papéis: '+html.escape(', '.join(sorted(roles)))+'</p>'+cert_section+f"<section><h2>Alertas de certificados</h2><table><thead><tr><th>Severidade</th><th>Estado</th><th>Mensagem</th><th>Reconhecido por</th><th>Ação</th></tr></thead><tbody>{''.join(alert_rows)}</tbody></table></section>"+f"<section><h2>Solicitações administrativas</h2><table><thead><tr><th>ID</th><th>Tipo</th><th>Máquina</th><th>Solicitante</th><th>Estado</th><th>Aprovador</th><th>Ação</th></tr></thead><tbody>{''.join(request_rows)}</tbody></table></section>"+f"<section><h2>Histórico de fingerprints</h2><table><thead><tr><th>Certificado</th><th>Origem</th><th>Fingerprint</th><th>Primeira</th><th>Última</th><th>Validade</th></tr></thead><tbody>{hist_rows}</tbody></table></section>"+''.join(cards)+'</body></html>').encode()

class H(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args): print(fmt%args,flush=True)
    def out(self,obj,status=200,ctype='application/json; charset=utf-8',headers=None):
        raw=obj if isinstance(obj,bytes) else json.dumps(obj,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type',ctype); self.send_header('Content-Length',str(len(raw))); self.send_header('Cache-Control','no-store')
        for k,v in (headers or {}).items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(raw)
    def body(self):
        n=int(self.headers.get('Content-Length','0') or 0)
        if n<0 or n>MAX_BODY: raise ValueError('body_too_large')
        return json.loads(self.rfile.read(n).decode() or '{}')
    def form(self):
        n=int(self.headers.get('Content-Length','0') or 0)
        if n<0 or n>MAX_BODY: raise ValueError('body_too_large')
        return parse_qs(self.rfile.read(n).decode('utf-8','strict'))
    def admin_session(self,required_role=None,form=None):
        actor,roles,_=admin_context(self.headers)
        if not actor or not roles: raise PermissionError('forbidden')
        if required_role and required_role not in roles: raise PermissionError('role_required:'+required_role)
        token=cookie_token(self.headers)
        if not validate_session(token,actor): raise PermissionError('invalid_session')
        if form is not None:
            supplied=(form.get('csrf_token') or [''])[0]
            if not hmac.compare_digest(supplied,csrf_for(token)): raise PermissionError('invalid_csrf')
        return actor,roles,token
    def redirect(self,location='/'):
        self.send_response(303); self.send_header('Location',location); self.send_header('Cache-Control','no-store'); self.end_headers()
    def do_GET(self):
        p=urlparse(self.path)
        if p.path=='/health': return self.out({'ok':True,'service':'machine-controller','database':'postgresql'})
        if p.path=='/':
            actor,roles,_=admin_context(self.headers)
            if not actor or not roles: return self.out({'ok':False,'error':'forbidden'},403)
            token=cookie_token(self.headers); headers={}
            if not validate_session(token,actor): token=issue_session(actor); headers['Set-Cookie']=session_cookie(token)
            return self.out(dashboard(actor,roles,csrf_for(token)),200,'text/html; charset=utf-8',headers)
        if p.path in {'/api/machines','/api/certificates','/api/certificates/history','/api/certificates/alerts'}:
            actor,roles,_=admin_context(self.headers)
            if not actor or 'viewer' not in roles:return self.out({'ok':False,'error':'forbidden'},403)
            c=con()
            if p.path=='/api/machines': items=[dict(r) for r in c.execute('select machine_id,hostname,state,last_seen,policy_version,message from machines order by hostname')]
            elif p.path=='/api/certificates':
                items=[]
                for r in c.execute('select hostname,inventory_json from machines order by hostname'):
                    inv=json.loads(r['inventory_json'] or '{}'); items.extend([dict(x,machine=r['hostname']) for x in inv.get('components',[]) if x.get('kind')=='certificate'])
            elif p.path=='/api/certificates/history': items=[dict(r) for r in c.execute('select * from certificate_history order by last_seen desc,id desc limit 1000')]
            else: items=[dict(r) for r in c.execute("select * from certificate_alerts order by case state when 'open' then 0 else 1 end,updated_at desc,id desc limit 1000")]
            c.close(); return self.out({'ok':True,'items':items})
        if p.path=='/api/policy':
            mid=parse_qs(p.query).get('machine_id',[''])[0]
            try: require_remote_machine(self.headers,mid)
            except Exception as e: return self.out({'ok':False,'error':str(e)},403)
            c=con(); row=c.execute('select policy_version,policy_json,state from machines where machine_id=?',(mid,)).fetchone(); c.close()
            if not row:return self.out({'ok':False,'error':'not_found'},404)
            return self.out({'ok':True,'policy_version':row['policy_version'],'policy':json.loads(row['policy_json'] or '{}'),'state':row['state']})
        return self.out({'ok':False,'error':'not_found'},404)
    def do_POST(self):
        try:
            if self.path=='/api/inventory':
                d=self.body(); mid=((d.get('payload') or {}).get('machine_id') or ''); require_remote_machine(self.headers,mid); return self.out(upsert_inventory(d),202)
            if self.path=='/api/guardian/event':
                d=self.body(); require_remote_machine(self.headers,d.get('machine_id','')); c=con(); c.execute('insert into guardian_events(machine_id,created_at,severity,event,message,detail_json) values(?,?,?,?,?,?)',(d.get('machine_id',''),now(),d.get('severity','info'),d.get('event',''),d.get('message',''),json.dumps(d.get('detail') or {},ensure_ascii=False))); c.commit(); c.close(); return self.out({'ok':True},202)
            if self.path=='/api/policy/applied':
                d=self.body(); mid=str(d.get('machine_id') or ''); require_remote_machine(self.headers,mid); ver=int(d.get('policy_version') or 0); c=con(); row=c.execute('select policy_version from machines where machine_id=?',(mid,)).fetchone()
                if not row or int(row['policy_version'])!=ver: c.close(); raise ValueError('policy_version_mismatch')
                c.execute('update machines set state=?,message=? where machine_id=?',('active','Política assinada aplicada; ações do Executor permanecem bloqueadas.',mid)); c.commit(); c.close(); return self.out({'ok':True,'state':'active'},202)
            if self.path=='/api/certificate/renew':
                d=self.body(); mid=str(d.get('machine_id') or ''); remote=require_remote_machine(self.headers,mid); old_serial=normalize_serial(self.headers.get('X-SSL-Client-Serial')); return self.out({'ok':True,**issue_certificate_renewal(mid,old_serial,str(d.get('csr_pem') or ''))},201)
            if self.path=='/api/certificate/renew/ack':
                d=self.body(); mid=str(d.get('machine_id') or ''); remote=require_remote_machine(self.headers,mid); presented=normalize_serial(self.headers.get('X-SSL-Client-Serial')); requested_new=normalize_serial(d.get('new_serial'))
                if presented!=requested_new: raise ValueError('new_certificate_not_presented')
                return self.out(finalize_certificate_renewal(mid,requested_new,d.get('old_serial'),str(d.get('renewal_id') or '')),202)
            form=self.form(); source_ip=(self.headers.get('X-Real-IP') or self.client_address[0])
            if self.path=='/admin/policy/request':
                actor,roles,_=self.admin_session('maintainer',form); mid=(form.get('machine_id') or [''])[0]; selected=form.get('monitor',[]); selections=[{'id':x,'monitor':True,'guard':True if str(x).startswith(('certificate:','systemd:')) else False,'backup':True if 'backup' in str(x).lower() else False} for x in selected]; create_policy_request(mid,selections,actor,source_ip); return self.redirect('/')
            if self.path=='/admin/requests/approve':
                actor,roles,_=self.admin_session('approver',form); approve_request((form.get('request_id') or [''])[0],actor,source_ip); return self.redirect('/')
            if self.path=='/admin/alerts/ack':
                actor,roles,_=self.admin_session('operator',form); acknowledge_alert((form.get('alert_id') or ['0'])[0],actor,(form.get('note') or [''])[0],source_ip); return self.redirect('/')
            return self.out({'ok':False,'error':'not_found'},404)
        except PermissionError as e:return self.out({'ok':False,'error':str(e)},403)
        except Exception as e:return self.out({'ok':False,'error':type(e).__name__,'message':str(e)[:300]},400)

if __name__=='__main__': init(); ThreadingHTTPServer((HOST,PORT),H).serve_forever()
