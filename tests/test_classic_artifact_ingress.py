#!/usr/bin/env python3
import argparse,json,re
from pathlib import Path
import jsonschema

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',default='/srv/cloudif-v2');a=ap.parse_args();r=Path(a.root)
    schema=json.load(open(r/'contratos/classic-artifact-ingress.schema.json'));jsonschema.Draft202012Validator.check_schema(schema)
    cfg=json.load(open(r/'config/classic-artifact-ingress.json'));jsonschema.validate(cfg,schema)
    sock=(r/'deploy/systemd/cloudiff-v2-artifact-classic-ingress.socket').read_text();svc=(r/'deploy/systemd/cloudiff-v2-artifact-classic-ingress.service').read_text();inst=(r/'deploy/install_classic_artifact_ingress.sh').read_text()
    aw=(r/'src/agent/artifact_engine.cpp').read_text();ah=(r/'include/cloudiff/artifact_engine.hpp').read_text();bw=(r/'src/worker/classic_build_worker.cpp').read_text();bh=(r/'include/cloudiff/classic_build_worker.hpp').read_text()
    assert 'ListenStream=10.62.91.2:18228' in sock and 'IPAddressAllow=10.62.91.3/32' in sock and 'IPAddressDeny=any' in sock
    assert 'systemd-socket-proxyd 127.0.0.1:18226' in svc and 'IPAddressAllow=127.0.0.0/8' in svc and 'IPAddressDeny=any' in svc
    assert 'cloudif-artifact-executor-v2.internal' in inst and 'allow 10.62.92.7;' in inst and 'proxy_pass http://10.62.91.2:18228/v1/build;' in inst
    assert cfg['legacyContinuity']['sharedHost']=='cloudif-artifact-executor.internal' and cfg['legacyContinuity']['redirectForbidden'] is True
    assert 'std::string classic_token;' in ah and 'CLOUDIFF_ARTIFACT_CLASSIC_TOKEN' in aw
    assert 'classic_token_required' in aw and 'artifact_token_scope' in aw
    assert 'classic_request=path=="/v1/build"&&requested_profile=="classic-static-v2"' in aw
    assert 'cloudif-artifact-executor-v2.internal' in bh and 'cloudif-artifact-executor-v2.internal' in bw
    assert 'cloudif-artifact-executor.internal' not in bh
    assert 'CLOUDIFF_ARTIFACT_CLASSIC_TOKEN=' not in inst and re.search(r'openssl rand',inst) is None
    assert 'ARTIFACT_PREVIOUS=/opt/cloudiff-v2/artifact-shadow-previous' in inst and 'WORKER_PREVIOUS=/opt/cloudiff-v2/build-worker-previous' in inst
    assert 'rm -f "/etc/systemd/system/$SOCKET_UNIT" "/etc/systemd/system/$SERVICE_UNIT"' in inst
    assert '18227' not in json.dumps(cfg) and '18227' not in sock and '18227' not in inst
    print('CLASSIC_ARTIFACT_INGRESS_OFFLINE=PASS')
if __name__=='__main__':main()
