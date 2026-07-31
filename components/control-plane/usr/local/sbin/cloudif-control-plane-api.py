#!/usr/bin/env python3
import os,sqlite3,json,hmac
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse
DB=os.environ.get('CLOUDIF_CONTROL_DB','/var/lib/cloudif/control-plane/control-plane.db')
TOKEN=os.environ.get('CLOUDIF_CONTROL_TOKEN','')
HOST=os.environ.get('CLOUDIF_CONTROL_HOST','127.0.0.1'); PORT=int(os.environ.get('CLOUDIF_CONTROL_PORT','18197'))
def rows(q,args=()):
    con=sqlite3.connect(f'file:{DB}?mode=ro',uri=True,timeout=5);con.row_factory=sqlite3.Row
    try:return [dict(r) for r in con.execute(q,args)]
    finally:con.close()
class H(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def sendj(self,code,data):
        raw=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def auth(self):
        got=self.headers.get('Authorization','');expected='Bearer '+TOKEN
        return bool(TOKEN) and hmac.compare_digest(got,expected)
    def do_GET(self):
        p=urlparse(self.path).path
        if p=='/health':
            try:
                meta=rows("select value from registry_meta where key='synced_at'")
                self.sendj(200,{'ok':True,'service':'cloudif-control-plane','synced_at':meta[0]['value'] if meta else None});return
            except Exception as e:self.sendj(503,{'ok':False,'error':'registry_unavailable'});return
        if not self.auth():self.sendj(401,{'ok':False,'error':'unauthorized'});return
        if p=='/v1/projects':
            data=rows('select * from projects order by slug');self.sendj(200,{'ok':True,'projects':data,'count':len(data)});return
        if p.startswith('/v1/projects/'):
            slug=p.split('/',3)[3]
            ps=rows('select * from projects where slug=?',(slug,))
            if not ps:self.sendj(404,{'ok':False,'error':'not_found'});return
            cs=rows('select connector,enabled,status,config_json from project_connectors where project_id=? order by connector',(ps[0]['project_id'],))
            acl=rows('select subject_type,subject,role from project_acl where project_id=? order by subject_type,subject',(ps[0]['project_id'],))
            self.sendj(200,{'ok':True,'project':ps[0],'connectors':cs,'acl':acl});return
        self.sendj(404,{'ok':False,'error':'not_found'})
ThreadingHTTPServer((HOST,PORT),H).serve_forever()
