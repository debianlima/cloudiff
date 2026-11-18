#!/usr/bin/env python3
"""Safe partial G3 Docker invariant test, intended for SSH user cti on Hospedagem.

No production mounts, Docker credentials, public ports, build, pull or secrets.
Only disposable prefixed resources. 0.2 CPU/64 MiB per test container.
"""
import argparse
import hashlib
from contextlib import nullcontext
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid


def run(*args, timeout=15, check=True):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError('controlled_command_failed code='+str(result.returncode)+ ' cmd='+str(args[:2]))
    return result


def record(stage, status, detail=''):
    print(json.dumps({'stage': stage, 'status': status, 'detail': detail}, sort_keys=True), flush=True)


def inspect(name):
    return json.loads(run('docker', 'inspect', name, timeout=8).stdout)[0]


def network_info(name, network):
    return inspect(name)['NetworkSettings']['Networks'].get(network)


def main(journal_smoke=False):
    if socket.gethostname() != 'hospedagem' or os.geteuid() == 0:
        raise RuntimeError('refusing_wrong_host_or_root_identity')
    ident = run('id','-un').stdout.strip()
    if ident != 'cti':
        raise RuntimeError('refusing_unexpected_user')
    # Verify all inputs and local source availability before any Docker effect.
    if journal_smoke:
        modules=pathlib.Path(__file__).resolve().parents[1]/'components/runtime/current-apps/komodo-agent-current'
        if not all((modules / name).is_file() for name in
                   ('cloudif_publication_effect_gate.py','cloudif_publication_recovery_journal.py')):
            raise RuntimeError('journal_source_modules_not_staged')
        sys.path.insert(0,str(modules))
        from cloudif_publication_effect_gate import make_publication_gate
        from cloudif_publication_recovery_journal import PublicationRecoveryJournal
    if run('docker','image','inspect','postgres:15-bookworm',check=False).returncode:
        raise RuntimeError('cached_image_not_present_do_not_pull')
    tag = uuid.uuid4().hex[:12]
    net='pgh-dev01-g3-'+tag
    old='pgh-dev01-prev-'+tag
    hn='pgh-dev01-hn-'+tag
    alias='pgh-dev01-active-'+tag
    owned=[old,hn]
    for name in [net]+owned:
        if run('docker','inspect',name,check=False).returncode==0:
            raise RuntimeError('resource_collision_refuse')
    tempfile_dir=tempfile.mkdtemp(prefix='pgh-dev01-g3-', dir='/tmp')
    os.chmod(tempfile_dir,0o700)
    marker=pathlib.Path(tempfile_dir)/'runtime.env'
    network_created=False
    try:
        marker.write_text('STAGE=hn\n')
        os.chmod(marker,0o600)
        run('docker','network','create','--internal','--driver','bridge',
            '--label','org.pgh.scope=disposable','--label','org.pgh.agent=dev01',net,
            timeout=24)
        network_created=True
        record('private_network','PASS','internal_bridge_no_host_ports')
        common=['docker','create','--pull=never','--read-only','--cap-drop=ALL',
            '--security-opt','no-new-privileges:true','--pids-limit','24','--cpus','0.20',
            '--memory','64m','--memory-swap','64m','--user',f'{os.getuid()}:{os.getgid()}',
            '--label','org.pgh.scope=disposable','--label','org.pgh.agent=dev01',
            '--network',net]
        command=['--entrypoint','/bin/sh','postgres:15-bookworm','-c','exec sleep 120']
        run(*(common+['--name',old,'--network-alias',alias]+command), timeout=18)
        run(*(common+['--name',hn,'--network-alias',hn,
                      '--mount',f'type=bind,source={tempfile_dir},target=/run/cloudif,readonly']+command),timeout=18)
        run('docker','start',old,timeout=18)
        run('docker','start',hn,timeout=18)
        old_id=inspect(old)['Id']
        hn_id=inspect(hn)['Id']
        assert hn_id!=old_id and inspect(hn)['State']['Running']
        assert alias in network_info(old,net)['Aliases']
        record('isolated_stages','PASS','two_nonprivileged_64m_0.2cpu_containers_running')
        if run('docker','exec',hn,'cat','/run/cloudif/runtime.env',timeout=8).stdout != 'STAGE=hn\n':
            raise RuntimeError('private_bind_initial_read_failed')
        gate=nullcontext(None)
        if journal_smoke:
            # Exact PR41 modules were preflighted and imported before any
            # test container or network was created; no installed worker used.
            journal_dir=pathlib.Path(tempfile_dir)/'journal-private'
            journal_dir.mkdir(mode=0o700)
            number=800000000+(int(tag[:8],16)%90000000)
            project='pgh-g3-'+tag
            canonical_target=f'cloudif-p{number}-d3-web'
            def observe_effect(row):
                # Synthetic journal identity is mapped solely to test-labeled
                # Docker containers, NEVER an active CloudIFF production name.
                if (row['project']!=project or row['kind']!='production_release'
                        or row['public_number']!=number
                        or row['target_container']!=canonical_target):
                    raise RuntimeError('journal_fixture_identity_mismatch')
                target_state=inspect(hn)
                previous_state=inspect(old)
                attached=network_info(hn,net)
                current=run('docker','exec',hn,'cat','/run/cloudif/runtime.env',timeout=8).stdout
                if (target_state['Id']!=hn_id or not target_state['State']['Running']
                        or previous_state['State']['Running']
                        or not attached or alias not in attached['Aliases']
                        or network_info(old,net) is not None
                        or current!='STAGE=pn\n'):
                    raise RuntimeError('docker_fixture_evidence_inconsistent')
                proof={key:row[key] for key in
                       ('operation_id','project','kind','public_number','publication_number','target_container')}
                proof.update({'docker_hn_id':hn_id,'docker_previous_id':old_id,
                              'active_alias_on_hn':True,'prior_stopped':True,
                              'effective_environment':'STAGE=pn'})
                return hashlib.sha256(json.dumps(proof,sort_keys=True,
                    separators=(',',':')).encode()).hexdigest()
            def fixture_verifier(row,phase,digest):
                # This is a test-only local Docker observer, NOT authenticated
                # production evidence or a cross-host distributed lease.
                return phase=='committed' and digest==observe_effect(row)
            gate=make_publication_gate(
                mode='strict',db_path=str(journal_dir/'journal.sqlite'),
                lock_dir=str(journal_dir),project=project,kind='production_release',
                public_number=number,publication_number=1,target=canonical_target,
                evidence_provider=observe_effect,evidence_verifier=fixture_verifier)
        with gate as active_gate:
            temp_marker=pathlib.Path(tempfile_dir)/'runtime.env.next'
            temp_marker.write_text('STAGE=pn\n')
            os.chmod(temp_marker,0o600)
            os.replace(temp_marker,marker)
            if run('docker','exec',hn,'cat','/run/cloudif/runtime.env',timeout=8).stdout != 'STAGE=pn\n':
                raise RuntimeError('directory_bind_atomic_replace_not_observed')
            run('docker','restart','--time','2',hn,timeout=25)
            if inspect(hn)['Id'] != hn_id:
                raise RuntimeError('candidate_identity_changed_on_restart')
            if run('docker','exec',hn,'cat','/run/cloudif/runtime.env',timeout=8).stdout != 'STAGE=pn\n':
                raise RuntimeError('runtime_env_not_effective_after_restart')
            record('runtime_environment','PASS','directory_bind_atomic_replace_and_restart_same_container_id')
            run('docker','network','disconnect',net,old,timeout=12)
            run('docker','network','disconnect',net,hn,timeout=12)
            run('docker','network','connect','--alias',hn,'--alias',alias,net,hn,timeout=12)
            before_stop=network_info(hn,net)
            if inspect(hn)['Id'] != hn_id or not before_stop or alias not in before_stop['Aliases']:
                raise RuntimeError('alias_switch_or_identity_invariant_failed')
            if network_info(old,net) is not None:
                raise RuntimeError('old_production_still_has_active_network_alias')
            run('docker','stop','--time','2',old,timeout=18)
            if inspect(old)['State']['Running']:
                raise RuntimeError('old_production_not_stopped')
            if run('docker','exec',hn,'getent','hosts',alias,timeout=9).returncode:
                raise RuntimeError('private_network_alias_resolution_failed')
            if inspect(hn)['Id'] != hn_id:
                raise RuntimeError('promotion_changed_candidate_identity')
            record('alias_promotion','PASS','active_alias_switched_old_stopped_same_hn_id')
            if journal_smoke:
                active_gate.finish()
        if journal_smoke:
            with PublicationRecoveryJournal(journal_dir/'journal.sqlite') as check:
                if check.unresolved():
                    raise RuntimeError('unexpected_pending_journal_after_real_docker_proof')
                row=check.con.execute('select phase,verification_sha256 from stage_publication_operation_journal').fetchone()
                if not row or row['phase']!='committed' or len(row['verification_sha256'])!=64:
                    raise RuntimeError('journal_success_not_verified')
            record('real_docker_with_journal','PASS',
                   'strict_test_only_evidence_verified_and_committed_same_hn_id')
    finally:
        for n in reversed(owned):
            run('docker','rm','-f',n,timeout=20,check=False)
        if network_created:
            run('docker','network','rm',net,timeout=16,check=False)
        shutil.rmtree(tempfile_dir,ignore_errors=True)
        residues=[]
        for n in owned:
            if run('docker','inspect',n,timeout=8,check=False).returncode==0:
                residues.append('container')
        if network_created and run('docker','network','inspect',net,timeout=8,check=False).returncode==0:
            residues.append('network')
        record('cleanup','PASS' if not residues else 'FAIL', 'no_test_resources_remaining' if not residues else 'unexpected_disposable_residue')
        if residues:
            raise RuntimeError('cleanup_incomplete')
    record('result','PASS','disposable_invariants_only_no_production_rollback_or_distributed_journal_claim')


def entrypoint():
    parser=argparse.ArgumentParser(description='Disposal-only Docker Hn->Pn alias and env smoke test; read-only plan by default.')
    parser.add_argument('--execute',action='store_true',help='Use only after owner/lock approval on Hospedagem.')
    parser.add_argument('--journal-smoke',action='store_true',help='On --execute only, use a disposable SQLite journal with test-only Docker proof.')
    args=parser.parse_args()
    if not args.execute:
        record('plan','READ_ONLY','requires --execute, approved G0 lock, cached image; creates two 64MiB/0.2CPU disposable containers and one internal network, then cleans up')
        return
    # Never add more pressure to an already busy production Docker host.
    cpus=os.cpu_count() or 4
    if os.getloadavg()[0] > max(4.0,1.5*cpus):
        raise RuntimeError('host_cpu_load_above_disposable_budget')
    available=0
    for line in pathlib.Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemAvailable:'):
            available=int(line.split(':',1)[1].split()[0])//1024
            break
    if available < 2048:
        raise RuntimeError('host_memory_below_disposable_budget')
    if shutil.disk_usage('/tmp').free < 1*1024**3:
        raise RuntimeError('host_disk_below_disposable_budget')
    main(journal_smoke=args.journal_smoke)


if __name__=='__main__':
    try:
        entrypoint()
    except Exception as err:
        record('result','FAIL',type(err).__name__+':'+str(err)[:100])
        sys.exit(1)
