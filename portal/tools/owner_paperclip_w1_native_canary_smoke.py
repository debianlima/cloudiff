#!/usr/bin/env python3
"""Isolated, short-lived Paperclip native-image smoke on Mauricio ONLY.

No host ports, no production networks, no production volumes, no credentials.
Does NOT authorize a live W1 cutover or prove authentication/browser E2E.
"""
from __future__ import annotations
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import time

BASE=Path("/srv/cloudif/offline-builds/paperclip-w1-1025-dfcaaf831438")
COMMIT="dfcaaf831438cf0402d54a5ede388c3dc66bf222"
IMAGE="cloudif/paperclip-w1-1025-native:dfcaaf831438"
CONTAINER="cloudif-paperclip-1025-native-smoke-dfcaaf83"
VOLUME="cloudif-paperclip-1025-native-smoke-data-dfcaaf83"
MARKER="pgh-infra02-paperclip-w1-native-smoke"
HTML_ASSET=re.compile(r"""(?:src|href)=["'](/assets/[A-Za-z0-9_.-]+\.(?:js|css))["']""")
PROOF=BASE/"native-canary-smoke-proof.json"

def run(argv:list[str], timeout:int=25, result:bool=True) -> subprocess.CompletedProcess:
    return subprocess.run(argv,stdout=subprocess.PIPE if result else subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL,timeout=timeout,check=False,text=True)

def inspect_image()->str:
    p=run(["docker","image","inspect",IMAGE,"--format","{{.Id}}"],15)
    return p.stdout.strip() if p.returncode==0 else ""

def already_exists(kind:str,name:str)->bool:
    args=(["docker","inspect",name] if kind=="container"
          else ["docker","volume","inspect",name])
    return run(args,15,False).returncode==0

def check_host()->None:
    if os.geteuid()!=0 or socket.gethostname().split(".")[0]!="mauricio":
        raise ValueError("BLOCKED_AUTHORIZED_MAURICIO_ROOT_REQUIRED")
    if not BASE.is_dir() or BASE.is_symlink():
        raise ValueError("BLOCKED_ISOLATED_WORKSPACE_NOT_FOUND")
    if not (BASE/"source").is_dir():
        raise ValueError("BLOCKED_SOURCE_NOT_AVAILABLE")
    sha=run(["git","-C",str(BASE/"source"),"rev-parse","HEAD"],12)
    if sha.returncode!=0 or sha.stdout.strip()!=COMMIT:
        raise ValueError("BLOCKED_SOURCE_COMMIT_MISMATCH")

def get_http(path:str)->tuple[int,str]:
    if not path.startswith("/") or ".." in path or "//" in path:
        raise ValueError("BLOCKED_PATH")
    target="http://127.0.0.1:3100"+path
    r=run(["docker","exec",CONTAINER,"curl","-sS","--max-time","8",
           "-o","/dev/null","-w","%{http_code}",target],15)
    return (int(r.stdout) if r.returncode==0 and r.stdout.isdecimal() else 0,
            "ok" if r.returncode==0 else "unavailable")

def get_html()->str:
    r=run(["docker","exec",CONTAINER,"curl","-sS","--max-time","8",
           "--max-filesize","131072","http://127.0.0.1:3100/"],15)
    return r.stdout[:131072] if r.returncode==0 else ""

def owned_resource(kind:str,name:str)->bool:
    args=(["docker","inspect","--format","{{index .Config.Labels \"org.cloudiff.pgh-test\"}}",name]
          if kind=="container" else
          ["docker","volume","inspect","--format","{{index .Labels \"org.cloudiff.pgh-test\"}}",name])
    r=run(args,12)
    return r.returncode==0 and r.stdout.strip()==MARKER

def smoke()->dict:
    check_host()
    image_id=inspect_image()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}",image_id):
        raise ValueError("BLOCKED_VERIFIED_NATIVE_IMAGE_NOT_AVAILABLE")
    if already_exists("container",CONTAINER) or already_exists("volume",VOLUME):
        raise ValueError("BLOCKED_TEST_RESOURCE_COLLISION")
    created_volume=False
    created_container=False
    proof={"schema":"cloudif-paperclip-native-canary-test/1","source_commit":COMMIT,
           "image_id":image_id,"host":"mauricio","container":CONTAINER,"network":"none",
           "no_ports":True,"temporary_volume":VOLUME,"http":{},"assets":[],
           "auth_login_tested":False,"browser_e2e":False,
           "production_mutated":False,"cleaned_up":False,"status":"NOT_READY"}
    try:
        v=run(["docker","volume","create",
               "--label","org.cloudiff.pgh-test="+MARKER,VOLUME],20)
        if v.returncode:raise ValueError("CANARY_VOLUME_CREATE_FAILED")
        created_volume=True
        start=["docker","run","-d","--name",CONTAINER,"--network","none",
               "--memory","4g","--cpus","2","--pids-limit","256",
               "--security-opt","no-new-privileges:true","--restart","no",
               "--label","org.cloudiff.pgh-test="+MARKER,
               "-v",VOLUME+":/paperclip",
               "-e","PAPERCLIP_DEPLOYMENT_MODE=authenticated",
               "-e","PAPERCLIP_DEPLOYMENT_EXPOSURE=private",
               "-e","PAPERCLIP_AUTH_DISABLE_SIGN_UP=true",
               "-e","PAPERCLIP_DB_BACKUP_ENABLED=false",
               "-e","PAPERCLIP_HOME=/paperclip",
               "-e","PAPERCLIP_INSTANCE_ID=preview-w1-1025-canary",
               "-e","PAPERCLIP_CONFIG=/paperclip/instances/preview-w1-1025-canary/config.json",
               "-e","HOST=0.0.0.0","-e","PORT=3100",IMAGE]
        p=run(start,55)
        if p.returncode or not re.fullmatch(r"[0-9a-f]{64}",p.stdout.strip()):
            raise ValueError("CANARY_CONTAINER_START_FAILED")
        created_container=True
        end=time.monotonic()+145
        while time.monotonic()<end:
            a,_=get_http("/api/health")
            b,_=get_http("/")
            proof["http"]={"/":b,"/api/health":a}
            if a==200 and b==200:break
            status=run(["docker","inspect","--format","{{.State.Status}}",CONTAINER],12)
            if status.returncode or status.stdout.strip()!="running":break
            time.sleep(5)
        if proof["http"].get("/")!=200 or proof["http"].get("/api/health")!=200:
            raise ValueError("CANARY_HTTP_ROOT_OR_API_NOT_READY")
        html=get_html()
        if "/src/main.tsx" in html or "/@vite/client" in html:
            raise ValueError("CANARY_RAW_VITE_NOT_BUILT")
        assets=HTML_ASSET.findall(html)
        if not assets:raise ValueError("CANARY_ASSET_MANIFEST_NOT_FOUND")
        for path in assets[:8]:
            status,_=get_http(path)
            proof["assets"].append({"path":path,"http":status})
            if status!=200:raise ValueError("CANARY_BUILT_ASSET_NOT_SERVED")
        proof["status"]="STATIC_BACKEND_HTTP_READY_AUTH_E2E_PENDING"
    except Exception as error:
        proof["error"]=str(error)[:180]
        proof["status"]="FAILED_NO_PUBLICATION"
    finally:
        cleaned=True
        if created_container:
            if owned_resource("container",CONTAINER):
                cleaned=run(["docker","rm","-f",CONTAINER],45).returncode==0 and cleaned
            else:cleaned=False
        if created_volume:
            if owned_resource("volume",VOLUME):
                cleaned=run(["docker","volume","rm",VOLUME],45).returncode==0 and cleaned
            else:cleaned=False
        proof["cleaned_up"]=cleaned
        if not cleaned:proof["status"]="FAILED_TEST_CLEANUP_REQUIRED"
    return proof

def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute",action="store_true",
                        help="explicitly authorize only an isolated Mauricio canary smoke")
    args=parser.parse_args()
    try:
        check_host()
        image_id=inspect_image()
        if not args.execute:
            print(json.dumps({"ready":bool(image_id),"execute_requested":False,
                              "host":"mauricio","nonproduction_only":True}))
            return 0 if image_id else 2
        with (BASE/"native-canary-smoke.lock").open("a+") as lk:
            fcntl.flock(lk,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if PROOF.exists():raise ValueError("BLOCKED_PROOF_EXISTS")
            out=smoke()
            with PROOF.open("x") as f:json.dump(out,f,indent=2,sort_keys=True)
            PROOF.chmod(0o600)
            print(json.dumps({"ok":out["status"]=="STATIC_BACKEND_HTTP_READY_AUTH_E2E_PENDING",
                              "state":out["status"],"http":out["http"],
                              "asset_count":len(out["assets"]),
                              "cleaned_up":out["cleaned_up"],
                              "auth_e2e":False,"proof":str(PROOF)}))
            return 0 if out["status"]=="STATIC_BACKEND_HTTP_READY_AUTH_E2E_PENDING" else 2
    except Exception as exc:
        print(json.dumps({"ok":False,"error":str(exc)[:140],"production_mutated":False}))
        return 2

if __name__=="__main__":
    raise SystemExit(main())
