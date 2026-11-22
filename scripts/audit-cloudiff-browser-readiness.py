#!/usr/bin/env python3
"""Audit CloudIFF URLs through the Forja Selenium WebDev browser.
Input: JSON array on stdin with objects containing at least `url`.
Output: JSONL. No credentials are read, written or persisted.
"""
import json,sys,time,urllib.request,urllib.error
BASE='http://127.0.0.1:14444';NPM='10.62.91.3'
def call(method,path,payload=None,timeout=15):
 data=None if payload is None else json.dumps(payload).encode()
 request=urllib.request.Request(BASE+path,data=data,method=method,headers={'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(request,timeout=timeout) as response:return response.status,response.read().decode()
 except urllib.error.HTTPError as exc:return exc.code,exc.read().decode(errors='ignore')
def main():
 targets=json.load(sys.stdin)
 rule=f'MAP *.cloudiff.duckdns.org {NPM}, MAP cloudiff.duckdns.org {NPM}, MAP authiff.duckdns.org {NPM}'
 caps={'capabilities':{'alwaysMatch':{'browserName':'chrome','acceptInsecureCerts':True,'pageLoadStrategy':'none','goog:chromeOptions':{'args':['--headless=new','--no-sandbox','--disable-dev-shm-usage','--window-size=1280,900','--host-resolver-rules='+rule]}}}}
 code,body=call('POST','/session',caps,25)
 if code!=200:raise SystemExit('session_create_'+str(code)+':'+body[:300])
 sid=(json.loads(body).get('value') or {}).get('sessionId')
 try:
  for target in targets:
   row=dict(target);row['browser_ok']=False
   try:
    code,_=call('POST',f'/session/{sid}/execute/sync',{'script':'window.location.href=arguments[0];return true;','args':[target['url']]},8)
    if code!=200:raise RuntimeError('set_location_http_'+str(code))
    time.sleep(float(target.get('settle_seconds') or 2.2))
    cu=call('GET',f'/session/{sid}/url',timeout=8);ti=call('GET',f'/session/{sid}/title',timeout=8)
    dom=call('POST',f'/session/{sid}/execute/sync',{'script':'return {ready:document.readyState,text:(document.body&&document.body.innerText||"").slice(0,260),html:(document.documentElement&&document.documentElement.outerHTML||"").length}','args':[]},8)
    if cu[0]!=200 or ti[0]!=200 or dom[0]!=200:raise RuntimeError('webdriver_read_failed')
    state=json.loads(dom[1]).get('value') or {}
    row.update(browser_ok=True,final_url=str(json.loads(cu[1]).get('value') or '')[:700],title=str(json.loads(ti[1]).get('value') or '')[:140],ready_state=state.get('ready'),text_head=' '.join(str(state.get('text') or '').split())[:240],html_bytes=int(state.get('html') or 0))
   except Exception as exc:row['error']=type(exc).__name__+':'+str(exc)[:180]
   print(json.dumps(row,ensure_ascii=False,sort_keys=True),flush=True)
 finally:
  try:call('DELETE',f'/session/{sid}',timeout=8)
  except Exception:pass
if __name__=='__main__':main()
