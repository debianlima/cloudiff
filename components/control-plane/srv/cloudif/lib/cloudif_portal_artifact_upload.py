#!/usr/bin/env python3
from __future__ import annotations

import http.client
import html
import json
import sqlite3
from typing import Any

BROKER_HOST='127.0.0.1'
BROKER_PORT=18206
MAX_UPLOAD_BYTES=64*1024*1024
TICKET_PREFIX='upt_'


def _json_body(response, limit: int = 65536) -> dict[str, Any]:
    raw=response.read(limit)
    try:data=json.loads(raw or b'{}')
    except Exception as exc:raise RuntimeError('workspace_broker_invalid_response') from exc
    return data if isinstance(data,dict) else {}


def ticket_status(ticket: str) -> dict[str, Any]:
    token=str(ticket or '').strip()
    if not token.startswith(TICKET_PREFIX) or len(token)>96:
        raise ValueError('invalid_upload_ticket')
    body=json.dumps({'upload_ticket':token},separators=(',',':')).encode('utf-8')
    conn=http.client.HTTPConnection(BROKER_HOST,BROKER_PORT,timeout=10)
    try:
        conn.request('POST','/v1/artifact/ticket/status',body=body,headers={'Content-Type':'application/json','Content-Length':str(len(body)),'Accept':'application/json'})
        response=conn.getresponse();data=_json_body(response)
    finally:
        conn.close()
    if response.status!=200 or not data.get('ok'):
        error=data.get('error') if isinstance(data,dict) else None
        code=str((error or {}).get('code') if isinstance(error,dict) else error or 'artifact_ticket_invalid')
        raise ValueError(code)
    result=data.get('result') or {}
    if not isinstance(result,dict):raise RuntimeError('artifact_ticket_status_invalid')
    return result


def project_allowed(user: dict[str, Any], slug: str) -> bool:
    import cloudif_portal_publications as publications
    con=sqlite3.connect(publications.DB);con.row_factory=sqlite3.Row
    try:return bool(publications._project_allowed(con,str(slug or ''),user))
    finally:con.close()


def safe_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    return {k:meta.get(k) for k in (
        'artifact_id','project_slug','filename','status','expected_size','expected_sha256',
        'received_bytes','expires_at','upload_ticket_status','upload_ticket_expires_at',
        'size','sha256','sealed_at','upload_transport',
    ) if meta.get(k) is not None}


def forward_upload(handler, ticket: str, expected_size: int) -> tuple[int,dict[str,Any]]:
    try:n=int(handler.headers.get('Content-Length','0') or 0)
    except Exception:raise ValueError('invalid_content_length')
    if n!=int(expected_size) or not (0<=n<=MAX_UPLOAD_BYTES):
        raise ValueError('artifact_size_mismatch')
    content_type=(handler.headers.get('Content-Type') or '').split(';',1)[0].strip().lower()
    if content_type!='application/octet-stream':raise TypeError('octet_stream_required')
    conn=http.client.HTTPConnection(BROKER_HOST,BROKER_PORT,timeout=180)
    try:
        conn.putrequest('POST','/v1/artifact/direct-upload')
        conn.putheader('Content-Type','application/octet-stream')
        conn.putheader('Content-Length',str(n))
        conn.putheader('X-CloudIF-Upload-Ticket',str(ticket))
        conn.putheader('Accept','application/json')
        conn.endheaders()
        remaining=n
        while remaining:
            chunk=handler.rfile.read(min(1024*1024,remaining))
            if not chunk:raise ConnectionError('client_upload_incomplete')
            conn.send(chunk);remaining-=len(chunk)
        response=conn.getresponse();data=_json_body(response)
        return response.status,data
    finally:
        conn.close()


def render_page(csrf_token: str) -> bytes:
    csrf=json.dumps(str(csrf_token or ''))
    markup='''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Enviar arquivo · CloudIFF</title><style>
:root{font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#171717;background:#f7f7f5}*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;padding:28px}main{width:min(680px,100%);background:#fff;padding:32px;border:1px solid #deded9;border-radius:18px}small{display:block;color:#676767}h1{font-size:clamp(1.7rem,5vw,2.35rem);letter-spacing:-.04em;margin:8px 0 10px}p{color:#5f5f5f;line-height:1.55}.meta{display:grid;gap:12px;margin:24px 0;padding:18px 0;border-block:1px solid #ecece7}.meta div{display:grid;gap:4px}.meta strong,.meta code{overflow-wrap:anywhere}label{display:grid;gap:8px;font-weight:700}input[type=file]{width:100%;padding:14px;border:1px solid #d7d7d2;border-radius:10px;background:#fff}button,a{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:0 16px;border-radius:10px;border:1px solid #222;background:#222;color:#fff;text-decoration:none;font:inherit;font-weight:750}button:disabled{opacity:.45;cursor:not-allowed}.actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}.status{margin-top:18px;padding:13px 14px;border-radius:10px;background:#f2f2ee;color:#353535}.status.bad{background:#fff0f0;color:#8a1c1c}.status.ok{background:#eef8f0;color:#17602c}progress{width:100%;height:8px;margin-top:14px}[hidden]{display:none!important}@media(max-width:560px){body{padding:14px}main{padding:22px;border-radius:14px}}@media(prefers-color-scheme:dark){:root{color:#f1f1ec;background:#0c0c0c}main,input[type=file]{background:#151515;border-color:#343434}p,small{color:#aaa}.meta{border-color:#2e2e2e}.status{background:#202020;color:#ddd}}
</style></head><body><main><small>UPLOAD DIRETO · CLOUDIFF</small><h1>Enviar arquivo para o artifact</h1><p>O arquivo vai direto para a CloudIFF. O servidor só sela o artifact se nome, tamanho e SHA-256 conferirem.</p><div class="meta"><div><small>Arquivo</small><strong id="filename">Validando ticket…</strong></div><div><small>Tamanho esperado</small><strong id="size">—</strong></div><div><small>SHA-256 esperado</small><code id="sha">—</code></div></div><label>Arquivo<input id="file" type="file" disabled></label><progress id="progress" value="0" max="100" hidden></progress><div class="status" id="status" role="status">Validando acesso…</div><div class="actions"><button id="send" type="button" disabled>Enviar arquivo</button><a href="/cloudiff/portal/?tab=projetos">Voltar aos projetos</a></div></main><script>
(()=>{const csrf=__CSRF__,key='cloudif-artifact-upload-ticket',hash=decodeURIComponent(location.hash.replace(/^#/,''));if(hash){sessionStorage.setItem(key,hash);history.replaceState(null,'',location.pathname)}const ticket=sessionStorage.getItem(key)||'',file=document.getElementById('file'),send=document.getElementById('send'),status=document.getElementById('status'),progress=document.getElementById('progress');let meta=null;const show=(text,kind='')=>{status.textContent=text;status.className='status'+(kind?' '+kind:'')};const api=async(url,opt={})=>{const r=await fetch(url,{credentials:'same-origin',...opt}),text=await r.text();let d={};try{d=JSON.parse(text)}catch(_){}if(!r.ok||!d.ok)throw new Error((d.error&&d.error.message)||d.error||('HTTP '+r.status));return d};async function load(){if(!ticket){show('Ticket ausente. Gere um novo link pelo agente.','bad');return}try{const d=await api('/cloudiff/portal/api/artifact-upload/status',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({upload_ticket:ticket})});meta=d.artifact;document.getElementById('filename').textContent=meta.filename;document.getElementById('size').textContent=new Intl.NumberFormat('pt-BR').format(meta.expected_size)+' bytes';document.getElementById('sha').textContent=meta.expected_sha256;if(meta.status==='sealed'){sessionStorage.removeItem(key);show('Artifact já está selado e pronto para o change set.','ok');return}file.disabled=false;show('Selecione exatamente o arquivo informado acima.')}catch(e){show(e.message||'Não foi possível validar o ticket.','bad')}}file.onchange=()=>{send.disabled=true;if(!meta||!file.files.length)return;const f=file.files[0];if(f.name!==meta.filename){show('O nome do arquivo selecionado não corresponde ao esperado.','bad');return}if(f.size!==Number(meta.expected_size)){show('O tamanho do arquivo selecionado não corresponde ao esperado.','bad');return}send.disabled=false;show('Arquivo conferido por nome e tamanho. Pronto para enviar.')} ;send.onclick=async()=>{const f=file.files[0];if(!f||!meta)return;send.disabled=true;file.disabled=true;progress.hidden=false;progress.value=20;show('Enviando arquivo diretamente para a CloudIFF…');try{await api('/cloudiff/portal/api/artifact-upload/content',{method:'POST',headers:{'Content-Type':'application/octet-stream','X-CSRF-Token':csrf,'X-CloudIF-Upload-Ticket':ticket},body:f});progress.value=100;sessionStorage.removeItem(key);show('Arquivo validado e artifact selado. Você pode voltar ao chat e continuar o change set.','ok')}catch(e){progress.hidden=true;file.disabled=false;send.disabled=false;show(e.message||'O upload não foi concluído.','bad')}};load()})();
</script></body></html>'''.replace('__CSRF__',csrf)
    return markup.encode('utf-8')
