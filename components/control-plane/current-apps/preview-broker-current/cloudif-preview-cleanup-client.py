#!/usr/bin/env python3
import json,os,urllib.request
u=os.environ.get('CLOUDIF_PREVIEW_CLEANUP_URL','http://127.0.0.1:18214/internal/cleanup');t=os.environ.get('CLOUDIF_PREVIEW_CLEANUP_TOKEN','')
req=urllib.request.Request(u,data=b'{}',method='POST',headers={'Authorization':'Bearer '+t,'Content-Type':'application/json'})
with urllib.request.urlopen(req,timeout=120) as r:x=json.load(r)
print(json.dumps(x,separators=(',',':')))
if not x.get('ok'):raise SystemExit(1)
