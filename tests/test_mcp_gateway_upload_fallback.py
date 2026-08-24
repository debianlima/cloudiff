#!/usr/bin/env python3
import argparse, ast, hashlib, runpy
from pathlib import Path

BASE_SHA='948e071ab08e45cd6a0683375669217aaaa76af5b8cc07bbd0092a7e1e71c846'

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--source',required=True); ap.add_argument('--base-source'); args=ap.parse_args()
    src=Path(args.source); text=src.read_text(); ast.parse(text)
    if args.base_source:
        assert sha(args.base_source)==BASE_SHA, (sha(args.base_source),BASE_SHA)
    required=[
      "artifact_import_upload_fallback=False;artifact_file_picker_fallback=False",
      "if tool=='workspace.artifact.import' and payload.get('code')=='host_file_param_not_hydrated':",
      "tool='workspace.artifact.upload.start';artifact_import_upload_fallback=True",
      "'automatic_upload_fallback':artifact_import_upload_fallback",
      "content['requested_tool']='workspace.artifact.import';content['effective_tool']='workspace.artifact.upload.start';content['automatic_fallback']=True",
      "content['file_params_hydrated']=False;content['filesystem_access_attempted']=False",
      "elif tool=='workspace.artifact.upload.file' and payload.get('code')=='host_file_param_not_hydrated':",
      "tool='workspace.artifact.upload.file.select';artifact_file_picker_fallback=True",
      "'_meta':{'openai/fileParams':['file']}"
    ]
    for needle in required: assert needle in text, needle
    assert text.count("event':'mcp_file_param_auto_fallback'")==1
    assert text.count("artifact_import_upload_fallback=True")==1
    # Load definitions without starting the server; verify the exact precondition that drives fallback.
    ns=runpy.run_path(str(src),run_name='cloudiff_mcp_gateway_v21_test')
    prepare=ns['_prepare_openai_file_param']; ToolInputError=ns['ToolInputError']
    args0={'slug':'laboratorio-de-hardware','file':'/mnt/data/arquivo.bin','filename':'arquivo.bin','expected_size':0,'expected_sha256':'0'*64}
    try: prepare('workspace.artifact.import',args0)
    except ToolInputError as exc:
        assert exc.payload.get('code')=='host_file_param_not_hydrated'
        assert exc.payload.get('fileShape',{}).get('classification') in {'path_like','absolute_path','mnt_data','sandbox','file_uri'}
    else: raise AssertionError('path-like import must raise host_file_param_not_hydrated before fallback handler')
    # Hydrated object remains accepted by the same prevalidation path.
    hydrated={**args0,'file':{'download_url':'https://files.oaiusercontent.com/object?sig=opaque','file_id':'file_1234567890abcdef'}}
    out=prepare('workspace.artifact.import',hydrated)
    assert isinstance(out['file'],dict) and out['file']['file_id']=='file_1234567890abcdef'
    print('MCP_GATEWAY_UPLOAD_FALLBACK_OFFLINE=PASS')
if __name__=='__main__': main()
