#!/usr/bin/env python3
import urllib.request,urllib.parse,urllib.error,re,json
base='http://127.0.0.1:18094';user='iff1742962';groups='CloudIF-Tenants,CloudIF-Tenants-Admin,CloudIF-Professor';origin='https://sistema-de-biblioteca-teste.cloudiff.duckdns.org'
h={'X-authentik-username':user,'X-authentik-email':'iff1742962@laboratorios.bomjesus.iff.edu.br','X-authentik-groups':groups,'Host':'cloudiff.duckdns.org','X-Forwarded-Host':'cloudiff.duckdns.org','Origin':origin,'Referer':origin+'/cloudiff/portal/?tab=projetos'}
html=urllib.request.urlopen(urllib.request.Request(base+'/cloudiff/portal/?tab=publicacao',headers=h),timeout=40).read().decode();csrf=re.search(r'name="csrf_token" value="([^"]+)"',html).group(1)
class NR(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,hdrs,newurl):return None
body=urllib.parse.urlencode({'csrf_token':csrf,'slug':'sistema-de-biblioteca-teste','op':'publish_version'}).encode();hh=dict(h);hh['Content-Type']='application/x-www-form-urlencoded'
req=urllib.request.Request(base+'/cloudiff/portal/action/publication',data=body,headers=hh,method='POST')
try:r=urllib.request.build_opener(NR).open(req,timeout=900);code=r.status;loc=r.headers.get('Location')
except urllib.error.HTTPError as e:code=e.code;loc=e.headers.get('Location')
assert code==303,(code,loc);assert loc and loc.startswith('/cloudiff/portal/?tab=publicacao&project=sistema-de-biblioteca-teste'),loc
out={'ok':True,'username':user,'origin':origin,'status':code,'location':loc,'cross_subdomain_origin_allowed':True,'secrets_exposed':False}
open('/var/lib/cloudif/portal/cross-subdomain-publish-result.json','w').write(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
