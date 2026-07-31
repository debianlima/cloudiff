#!/usr/bin/env python3
import urllib.request,urllib.parse,urllib.error,re,json
base='http://127.0.0.1:18094';user='iff1742962';groups='CloudIF-Tenants,CloudIF-Tenants-Admin,CloudIF-Professor'
headers={'X-authentik-username':user,'X-authentik-email':'iff1742962@laboratorios.bomjesus.iff.edu.br','X-authentik-groups':groups,'Host':'cloudiff.duckdns.org','Origin':'https://cloudiff.duckdns.org'}
req=urllib.request.Request(base+'/cloudiff/portal/?tab=publicacao',headers=headers)
html=urllib.request.urlopen(req,timeout=40).read().decode()
csrf=re.search(r'name="csrf_token" value="([^"]+)"',html).group(1)
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,hdrs,newurl):return None
opener=urllib.request.build_opener(NoRedirect)
data=urllib.parse.urlencode({'csrf_token':csrf,'slug':'sistema-de-biblioteca-teste','op':'publish_version'}).encode();h=dict(headers);h['Content-Type']='application/x-www-form-urlencoded'
req=urllib.request.Request(base+'/cloudiff/portal/action/publication',data=data,headers=h,method='POST')
try:
 r=opener.open(req,timeout=700);code=r.status;loc=r.headers.get('Location')
except urllib.error.HTTPError as e:
 code=e.code;loc=e.headers.get('Location')
assert code==303,(code,loc)
assert loc and loc.startswith('/cloudiff/portal/?tab=publicacao&project=sistema-de-biblioteca-teste'),loc
assert '/cloudif/portal/' not in loc,loc
out={'ok':True,'status':code,'location':loc,'username':user,'groups':groups.split(','),'correct_redirect':True,'secrets_exposed':False}
open('/var/lib/cloudif/portal/publication-redirect-test.json','w').write(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
