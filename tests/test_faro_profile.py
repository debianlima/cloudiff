#!/usr/bin/env python3
from pathlib import Path
import json
root=Path(__file__).resolve().parents[1]
x=json.load(open(root/'config/faro-node-profile.json'))
assert x['version']==2
assert x['role']=='edge'
assert set(['inventory','health','telemetry-host','portal-host','agent-auto-update']).issubset(x['capabilities'])
assert set(['build','runtime'])==set(x['excluded_capabilities'])
assert x['platform']=={'os':'ubuntu-server-26.04','arch':'x86_64','systemd':True,'virtualization':'kvm'}
r=x['requested_resources'];o=x['observed_resources'];g=x['resource_gates']
assert r['vcpu']==4 and r['ram_bytes']==8589934592 and r['disk_bytes']==214748364800
assert o['vcpu']==4 and o['ram_bytes']==7784714240 and o['configured_ram_bytes']==8589934592 and o['disk_bytes']==214748364800
assert o['lv_bytes']==212596686848 and o['root_filesystem_bytes']==208661176320
assert g['vcpu']=='pass'
assert g['ram']=='pass'
assert g['disk']=='pass'
assert r['status']=='satisfied'
assert x['recovery']=={'backup':'reinstall-from-scratch','automatic_reboot_default':True,'admin_can_disable_reboot':True}
assert x['portal']['desired_host'] is True and x['portal']['cutover']=='after-faro-onboarding-and-portal-shadow-gates'
assert x['monitoring']['hierarchy']=='environment>node>container>service'
print('FARO_PROFILE=PASS desired=4vCPU/8GiB/200GiB observed=4vCPU/DMI-8GiB/200GiB resources=PASS')
