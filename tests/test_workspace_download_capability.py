#!/usr/bin/env python3
import argparse, base64, hashlib, importlib.util, json, shutil, subprocess, tempfile, time
from pathlib import Path

BASE_MAIN_SHA='196b4452e85babca99fbbab611a38c49dfaaea377c36360d9f7d4c24c02aaf33'
BASE_HELPER_SHA='99bb293fd46c2db05413aefcd7b3707d13213d08faa77dd9eb68dabc372bbc99'
PATCHED_MAIN_SHA='cdb7d1a919dc83507ab68cf0ed4e4a0dc5ffcde5c42cf17b1956115d344c15bd'
PATCHED_HELPER_SHA='f760fa3cb7ebd2453f14de8ff892c4c02283c5e4b866e56ccf1b5ca268910608'

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load_helper(path):
    spec=importlib.util.spec_from_file_location('cloudif_workspace_artifact_p13',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--main-base',required=True);ap.add_argument('--helper-base',required=True);ap.add_argument('--patch',required=True);ap.add_argument('--source-dir');args=ap.parse_args()
    assert sha(args.main_base)==BASE_MAIN_SHA;assert sha(args.helper_base)==BASE_HELPER_SHA
    with tempfile.TemporaryDirectory(prefix='cloudiff-p13-ws-') as td:
        td=Path(td);shutil.copy2(args.main_base,td/'cloudif-workspace-broker.py');shutil.copy2(args.helper_base,td/'cloudif_workspace_artifact.py')
        with open(args.patch,'rb') as stdin:
            r=subprocess.run(['patch','--batch','--forward','-p1'],cwd=td,stdin=stdin,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        assert r.returncode==0,(r.stdout+r.stderr).decode('utf-8','replace')
        mainp=td/'cloudif-workspace-broker.py';helperp=td/'cloudif_workspace_artifact.py'
        assert sha(mainp)==PATCHED_MAIN_SHA;assert sha(helperp)==PATCHED_HELPER_SHA
        compile(mainp.read_bytes(),str(mainp),'exec');compile(helperp.read_bytes(),str(helperp),'exec')
        helper=load_helper(helperp)
        root=td/'artifacts';raw=b'cloudiff-p13-download\n';digest=hashlib.sha256(raw).hexdigest()
        meta=helper.start_artifact(str(root),'fixture-project','fixture.bin',len(raw),digest,3600);aid=meta['artifact_id']
        helper.append_chunk(str(root),'fixture-project',aid,0,base64.b64encode(raw).decode(),digest);sealed=helper.complete_artifact(str(root),'fixture-project',aid);assert sealed['status']=='sealed'
        try:helper.create_download_ticket(str(root),'other-project',aid,'tester',300)
        except helper.ArtifactError as e:assert e.code=='artifact_project_mismatch'
        else:raise AssertionError('project mismatch must fail')
        first=helper.create_download_ticket(str(root),'fixture-project',aid,'tester',300);t1=first['download_ticket'];assert t1.startswith('dlt_') and t1 not in (root/aid/'metadata.json').read_text()
        stored=json.loads((root/aid/'metadata.json').read_text())['download_ticket'];assert stored['sha256']==hashlib.sha256(t1.encode()).hexdigest();assert 'download_ticket' not in stored
        second=helper.create_download_ticket(str(root),'fixture-project',aid,'tester',300);t2=second['download_ticket'];assert t1!=t2
        try:helper.consume_download_ticket(str(root),t1)
        except helper.ArtifactError as e:assert e.code=='download_ticket_not_found'
        else:raise AssertionError('replaced ticket must fail')
        consumed=helper.consume_download_ticket(str(root),t2);assert Path(consumed['payload_path']).read_bytes()==raw;assert consumed['sha256']==digest;assert consumed['size']==len(raw)
        try:helper.consume_download_ticket(str(root),t2)
        except helper.ArtifactError as e:assert e.code=='download_ticket_used'
        else:raise AssertionError('second use must fail')
        third=helper.create_download_ticket(str(root),'fixture-project',aid,'tester',300);mp=root/aid/'metadata.json';data=json.loads(mp.read_text());data['download_ticket']['expires_at']=int(time.time())-1;mp.write_text(json.dumps(data,separators=(',',':')))
        try:helper.consume_download_ticket(str(root),third['download_ticket'])
        except helper.ArtifactError as e:assert e.code=='download_ticket_expired'
        else:raise AssertionError('expired ticket must fail')
        text=mainp.read_text()
        assert "path == '/v1/artifact/download/capability/read'" in text
        assert "if not self.local_client()" in text
        assert "X-CloudIF-Download-Ticket" in text
        assert "Content-Disposition" in text and "filename*=UTF-8''" in text
        assert "download_ticket_used','download_ticket_expired" in text and 'code=410' in text
        assert "'download_ticket':ticket" in helperp.read_text()
        assert "print(ticket" not in text and "print(ticket" not in helperp.read_text()
        if args.source_dir:
            src=Path(args.source_dir);assert sha(src/'cloudif-workspace-broker.py')==PATCHED_MAIN_SHA;assert sha(src/'cloudif_workspace_artifact.py')==PATCHED_HELPER_SHA
    print('WORKSPACE_DOWNLOAD_CAPABILITY_OFFLINE=PASS')
if __name__=='__main__':main()
