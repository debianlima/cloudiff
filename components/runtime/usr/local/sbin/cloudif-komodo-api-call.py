#!/usr/bin/env python3
import json, os, ssl, sys, urllib.request, urllib.error
from pathlib import Path

ENV="/etc/cloudif/komodo-agent.env"

def load_env():
    d={}
    if Path(ENV).exists():
        for line in Path(ENV).read_text(errors="ignore").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k,v=line.split("=",1)
                d[k.strip()] = v.strip().strip('"').strip("'")
    return d

def headers(env):
    h={
        "Accept":"application/json",
        "Content-Type":"application/json",
        "User-Agent":"CloudIF-Komodo-ApiCall-v30",
    }

    key = env.get("KOMODO_API_KEY") or env.get("KOMODO_BOOTSTRAP_API_KEY") or ""
    sec = env.get("KOMODO_API_SECRET") or env.get("KOMODO_BOOTSTRAP_API_SECRET") or ""
    tok = env.get("KOMODO_API_TOKEN") or env.get("KOMODO_BOOTSTRAP_TOKEN") or ""

    if key and sec:
        h["X-Api-Key"] = key
        h["X-Api-Secret"] = sec
    elif tok:
        h["Authorization"] = "Bearer " + tok
    else:
        # fallback: tenta Authentik via agente, mas Komodo já mostrou que isso dá Invalid user credentials.
        pass

    return h

def call(kind, op_type, params):
    env=load_env()
    base=(env.get("KOMODO_CORE_URL") or env.get("KOMODO_URL") or "http://10.62.91.2:9120").rstrip("/")
    endpoint={
        "read": env.get("KOMODO_READ_ENDPOINT","/read"),
        "write": env.get("KOMODO_WRITE_ENDPOINT","/write"),
        "execute": env.get("KOMODO_EXECUTE_ENDPOINT","/execute"),
    }[kind]
    url=base+endpoint

    payload={"type":op_type, "params": params}
    data=json.dumps(payload).encode()

    req=urllib.request.Request(url, data=data, headers=headers(env), method="POST")
    ctx=ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
            raw=r.read().decode("utf-8","ignore")
            try: parsed=json.loads(raw) if raw else {}
            except Exception: parsed={"raw":raw}
            print(json.dumps({"ok":True,"status":r.status,"url":url,"data":parsed}, ensure_ascii=False, indent=2))
            return 0
    except urllib.error.HTTPError as e:
        raw=e.read().decode("utf-8","ignore")
        try: parsed=json.loads(raw) if raw else {}
        except Exception: parsed={"raw":raw}
        print(json.dumps({"ok":False,"status":e.code,"url":url,"data":parsed}, ensure_ascii=False, indent=2))
        return 1
    except Exception as e:
        print(json.dumps({"ok":False,"status":0,"url":url,"error":str(e)}, ensure_ascii=False, indent=2))
        return 1

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: cloudif-komodo-api-call.py read|write|execute TipoOperacao '{json_params}'")
        sys.exit(2)

    kind=sys.argv[1]
    op=sys.argv[2]
    params=json.loads(sys.argv[3]) if len(sys.argv) >= 4 else {}
    sys.exit(call(kind, op, params))
