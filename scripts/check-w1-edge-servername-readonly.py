#!/usr/bin/env python3
"""Read-only NPM managed W1 server_name presence probe (Mauricio only).

Does not parse effective Nginx include graph, cert state, or config reload.
Outputs only known host coverage booleans, never configuration contents.
"""
import json,os,re,socket
from pathlib import Path

CONF=Path('/srv/cloudif/proxy/npm/data/nginx/custom/http.conf')
HOSTS={
    'agenda':'1020-w1-preview.cloudiff.duckdns.org',
    'cadales':'1022-w1-preview.cloudiff.duckdns.org',
    'cpuhub':'1021-w1-preview.cloudiff.duckdns.org',
    'labhardware':'1001-w1-preview.cloudiff.duckdns.org',
    'mvplanner':'1024-w1-preview.cloudiff.duckdns.org',
    'paperclip':'1025-w1-preview.cloudiff.duckdns.org',
    'silvipro':'1002-w1-preview.cloudiff.duckdns.org',
}

def summarize(content):
    # Known, static hostname allowlist and explicit config directive tokens.
    # No proxy_pass targets, cert paths, config fragments or customer data.
    names=[]
    for m in re.finditer(r'(?m)^\s*server_name\s+([^;\n]+);',content):
        names.extend(m.group(1).split())
    matches={name:{'exact_server_name_entries':names.count(host),
                   'textual_config_present':host in names} for name,host in HOSTS.items()}
    return {'schema':'w1-public-npm-servernames/1',
            'no_mutation':True,'secrets_printed':False,
            'effective_config_proven':False,'tls_verified':False,
            'application_health_verified':False,
            'all_known_w1_server_names_present':all(x['textual_config_present'] for x in matches.values()),
            'host_rules':matches}

def run():
    if socket.gethostname().split('.')[0].lower()!='mauricio':
        return {'status':'BLOCKED_WRONG_HOST','no_mutation':True,'secrets_printed':False}
    try:
        if CONF.stat().st_size>4*1024*1024 or not os.access(CONF,os.R_OK):
            return {'status':'BLOCKED_CONFIG_UNREADABLE_OR_TOO_LARGE','no_mutation':True,'secrets_printed':False}
        body=CONF.read_text(errors='replace')
    except OSError:
        return {'status':'BLOCKED_CONFIG_UNREADABLE_OR_TOO_LARGE','no_mutation':True,'secrets_printed':False}
    out=summarize(body);out['status']='METADATA_ONLY';return out
if __name__=='__main__':
    value=run();print(json.dumps(value,sort_keys=True,ensure_ascii=False))
    raise SystemExit(0 if value.get('all_known_w1_server_names_present') else 2)
