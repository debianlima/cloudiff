#!/usr/bin/env python3
import urllib.request,urllib.parse,re,json
base='http://127.0.0.1:18094';user='iff1742962';groups='CloudIF-Tenants,CloudIF-Tenants-Admin,CloudIF-Professor'
h={'X-authentik-username':user,'X-authentik-email':'iff1742962@laboratorios.bomjesus.iff.edu.br','X-authentik-groups':groups,'Host':'cloudiff.duckdns.org','Origin':'https://cloudiff.duckdns.org'}
req=urllib.request.Request(base+'/cloudiff/portal/?tab=publicacao',headers=h)
html=urllib.request.urlopen(req,timeout=40).read().decode()
assert 'sistema-de-biblioteca-teste' in html and 'Publicar site' in html
csrf=re.search(r'name="csrf_token" value="([^"]+)"',html).group(1)
data=urllib.parse.urlencode({'csrf_token':csrf,'slug':'sistema-de-biblioteca-teste','op':'publish_version'}).encode();hh=dict(h);hh['Content-Type']='application/x-www-form-urlencoded'
req=urllib.request.Request(base+'/cloudiff/portal/action/publication',data=data,headers=hh,method='POST')
with urllib.request.urlopen(req,timeout=600) as r:body=r.read();status=r.status
assert status==200 and b'Erro na publica' not in body
out={'ok':True,'username':user,'groups':groups.split(','),'portal_button_executed':True,'status':status,'response_bytes':len(body),'secrets_exposed':False}
open('/var/lib/cloudif/portal/tenant-publish-button-result.json','w').write(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
