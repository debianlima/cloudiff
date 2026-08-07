#!/usr/bin/env python3
import http.client,re,sys,json
HOST='10.62.92.7'; PORT=18094
checks=[]
def fetch(groups,tab='resumo'):
    c=http.client.HTTPConnection(HOST,PORT,timeout=12)
    c.request('GET',f'/cloudif/portal/?tab={tab}',headers={'X-authentik-username':'teste.cloudif','X-authentik-email':'teste@invalid.local','X-authentik-groups':groups})
    r=c.getresponse(); body=r.read().decode('utf-8','replace'); headers={k.lower():v for k,v in r.getheaders()}; c.close(); return r.status,headers,body
def ok(name,cond,detail=''):
    checks.append((name,bool(cond),detail)); print(('PASS' if cond else 'FAIL')+'|'+name+('|'+detail if detail else ''))
prof_status,prof_h,prof=fetch('CloudIF-Tenants|CloudIF-Professor')
admin_status,admin_h,admin=fetch('CloudIF-Tenants|CloudIF-Professor|CloudIF-Tenants-Admin')
ok('professor_http',prof_status==200,str(prof_status))
ok('admin_http',admin_status==200,str(admin_status))
ok('novo_layout','<nav class="nav"' in prof and 'class="app"' in prof)
ok('hero_professor','<main class="page"' in prof and 'class="page-head"' in prof)
ok('chip_professor','class="profile-card"' in prof and 'class="profile-role">Professor<' in prof)
ok('admin_visivel_professor','Administração' in prof and 'Administração do AD' not in prof)
ok('admin_visivel_admin','Administração do AD' in admin)
ok('chip_admin','class="profile-card"' in admin and 'class="profile-role">Administrador<' in admin)
ok('logout','/outpost.goauthentik.io/sign_out' in prof)
ok('skip_link','class="skip-link" href="#conteudo-principal"' in prof and 'id="conteudo-principal"' in prof)
ok('aria_current','aria-current="page"' in prof)
expected={'cache-control':'no-store','x-content-type-options':'nosniff','x-frame-options':'DENY','referrer-policy':'no-referrer','permissions-policy':'camera=()','content-security-policy':"frame-ancestors 'none'"}
for k,v in expected.items(): ok('header_'+k,v.lower() in prof_h.get(k,'').lower(),prof_h.get(k,''))
# one occurrence only for consolidated headers
for k in ('content-security-policy','x-frame-options','referrer-policy'): ok('single_'+k,list(prof_h).count(k)==1)
fail=sum(not x[1] for x in checks)
print(json.dumps({'tests':len(checks),'failures':fail}))
sys.exit(1 if fail else 0)
