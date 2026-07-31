#!/usr/bin/env python3
import json,sys
sys.path[:0]=['/srv/cloudif/lib','/srv/cloudif/app-pointers/portal-current']
import cloudif_portal_publications as p
u={'username':'iff1742962','groups':['CloudIF-Tenants-Admin','CloudIF-Professor'],'admin':True}
x=p.publish('sistema-de-biblioteca-teste',u)
open('/var/lib/cloudif/portal/publish-1009-result.json','w').write(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
assert x['ok'] and x['public_number']==1009
