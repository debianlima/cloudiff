#!/usr/bin/env python3
import json, os, ssl, subprocess, urllib.request
from pathlib import Path
STATE=Path('/var/lib/cloudif-machine-agent'); MID=STATE/'machine-id'; LAST=STATE/'last-inventory.json'; CURRENT=STATE/'current-inventory.json'; BASE=os.environ.get('CLOUDIF_MACHINE_CONTROLLER_URL','http://127.0.0.1:18110').rstrip('/'); URL=BASE+'/api/guardian/event'; AGENT_CA=os.environ.get('CLOUDIF_MACHINE_AGENT_CA',''); AGENT_CERT=os.environ.get('CLOUDIF_MACHINE_AGENT_CERT',''); AGENT_KEY=os.environ.get('CLOUDIF_MACHINE_AGENT_KEY','')
def send(sev,event,msg,detail=None):
    body={'machine_id':MID.read_text().strip() if MID.exists() else 'unknown','severity':sev,'event':event,'message':msg,'detail':detail or {}}
    try:
        req=urllib.request.Request(URL,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'},method='POST')
        if URL.startswith('https://'):
            ctx=ssl.create_default_context(cafile=AGENT_CA); ctx.load_cert_chain(certfile=AGENT_CERT,keyfile=AGENT_KEY)
            urllib.request.urlopen(req,timeout=10,context=ctx).read()
        else: urllib.request.urlopen(req,timeout=10).read()
    except Exception: pass
def main():
    rc=subprocess.run(['systemctl','is-active','cloudif-machine-harvester.timer'],capture_output=True,text=True).returncode
    if rc!=0: send('high','harvester_timer_inactive','Timer do Harvester inativo.'); raise SystemExit(1)
    if not LAST.exists(): send('warning','inventory_missing','Inventário ainda não foi enviado.'); raise SystemExit(0)
    age=int(__import__('time').time()-LAST.stat().st_mtime)
    if age>600:
        send('high','inventory_stale','Inventário atrasado.',{'age_seconds':age})
        subprocess.run(['systemctl','start','cloudif-machine-harvester.service'],timeout=90)
    else: send('info','guardian_ok','Harvester e inventário saudáveis.',{'age_seconds':age})
    if CURRENT.exists():
        try:
            inv=json.loads(CURRENT.read_text())
            certs=[x for x in inv.get('components',[]) if x.get('kind')=='certificate']
            alerts=[x for x in certs if x.get('state') in {'warning','critical','urgent','expired','error'}]
            for x in alerts:
                st=x.get('state'); sev='high' if st in {'urgent','expired','error'} else ('warning' if st=='critical' else 'info')
                send(sev,'certificate_'+st,f"Certificado {x.get('name')} em estado {st}.",{'name':x.get('name'),'source':x.get('source'),'days_remaining':x.get('days_remaining'),'not_after':x.get('not_after')})
        except Exception as exc:
            send('warning','certificate_inventory_error','Falha ao avaliar inventário de certificados.',{'error':type(exc).__name__})
if __name__=='__main__': main()
