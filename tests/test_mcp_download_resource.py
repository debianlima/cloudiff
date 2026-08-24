#!/usr/bin/env python3
import argparse, hashlib, runpy, shutil, subprocess, tempfile
from pathlib import Path
BASE_SHA='b218ec85083e0d3f1b6f0a02befa6210301363b5ac0e9c0630338825b67a7841'
PATCHED_SHA='f332023a009c80e831eadfebb1ef11b36084f36ed0bd4ce5255cead9bef86df8'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',required=True);ap.add_argument('--patch',required=True);ap.add_argument('--source');a=ap.parse_args()
    assert sha(a.base)==BASE_SHA
    with tempfile.TemporaryDirectory(prefix='cloudiff-p13-mcp-') as td:
        td=Path(td);target=td/'cloudif-mcp-gateway.py';shutil.copy2(a.base,target)
        with open(a.patch,'rb') as stdin:r=subprocess.run(['patch','--batch','--forward','-p1'],cwd=td,stdin=stdin,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        assert r.returncode==0,(r.stdout+r.stderr).decode('utf-8','replace')
        assert sha(target)==PATCHED_SHA;compile(target.read_bytes(),str(target),'exec')
        ns=runpy.run_path(str(target),run_name='cloudiff_mcp_download_test')
        tool=next(x for x in ns['TOOLS'] if x.get('name')=='workspace.artifact.download')
        assert ns['SCOPE_BY_TOOL']['workspace.artifact.download']=='workspace:change-set-plan'
        assert 'workspace.artifact.download' in ns['MCP_ONLY_TOOLS']
        assert 'workspace.artifact.download' not in ns['READ_ONLY_TOOLS']
        props=tool['inputSchema']['properties'];assert set(tool['inputSchema']['required'])=={'slug','artifact_id'};assert props['ttl_seconds']=={'type':'integer','minimum':60,'maximum':3600}
        out=tool['outputSchema'];assert 'transfer' in out['properties'];pattern=out['properties']['transfer']['properties']['content_ref']['pattern'];assert 'artifact-download/dlt_' in pattern
        text=target.read_text();start=text.index("elif name=='workspace.artifact.download':");end=text.index("elif name=='workspace.artifact.commit.plan':",start);branch=text[start:end]
        assert "workspace_broker_post('/v1/artifact/download/ticket'" in branch
        assert "content_ref=PUBLIC_ORIGIN+'/cloudiff/artifact-download/'" in branch
        assert "artifact.pop('download_ticket'" in branch
        assert 'oauth_token_exposed' in branch and "'resource_link'" in text
        assert 'print(' not in branch and 'audit_async' not in branch
        assert "'type':'resource_link'" in text and "'mimeType':'application/octet-stream'" in text
        if a.source:assert sha(a.source)==PATCHED_SHA and Path(a.source).read_bytes()==target.read_bytes()
    print('MCP_DOWNLOAD_RESOURCE_OFFLINE=PASS')
if __name__=='__main__':main()
