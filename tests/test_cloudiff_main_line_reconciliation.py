#!/usr/bin/env python3
import json, subprocess, sys
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
MAIN='bc4effd53ecd80912ea2a3a4e4b6efb4852af4a9'
PRE='32c3900383e619cbacb12af87fb5a4149630d678'
MERGE_BASE='8cc669ae5fba38d7148192b295af632cbd1b9be7'

def fail(msg):
    print('CLOUDIFF_T037_MAIN_LINE_RECONCILIATION=FAIL',msg)
    raise SystemExit(2)
def git(*args): return subprocess.run(['git','-C',str(ROOT),*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
def main():
    if git('merge-base','--is-ancestor',MAIN,'HEAD').returncode!=0: fail('main-not-ancestor')
    if git('merge-base','--is-ancestor',PRE,'HEAD').returncode!=0: fail('pre-branch-not-ancestor')
    evp=ROOT/'docs/reconciliation/cloudiff-main-line-reconciliation-v73.json'
    if not evp.exists(): fail('missing-evidence')
    ev=json.loads(evp.read_text(encoding='utf-8'))
    expected={'main_before':MAIN,'branch_before':PRE,'merge_base':MERGE_BASE,'target_only_commits':33,'main_only_commits':1}
    for k,v in expected.items():
        if ev.get('inventory',{}).get(k)!=v: fail('inventory:'+k)
    for g in ('DELTA_INVENTORY','LEARNING_PRESERVED','MAIN_ONLY_CLEANUP_PRESERVED','TARGET_LEARNING_PRESERVED','NO_RUNTIME_DEPLOY','RECONCILIATION_CLOSURE','DEPENDENCY_REFERENCES'):
        if ev.get('gates',{}).get(g)!='PASS': fail('gate:'+g)
    if ev.get('governance_delta',{}).get('from')!='1.0.4' or ev.get('governance_delta',{}).get('to')!='1.0.5': fail('governance-delta')
    skill=(ROOT/'skills/cloudiff/SKILL.md').read_text(encoding='utf-8')
    if 'versao: 0.1.28' not in skill: fail('skill-version')
    if 'versao_fixada: 1.0.5' not in skill: fail('governance-ref')
    comp=yaml.safe_load((ROOT/'competencias.yaml').read_text(encoding='utf-8')) or {}
    rows=comp.get('competencias',comp if isinstance(comp,list) else [])
    hits=[x for x in rows if isinstance(x,dict) and x.get('id')=='governanca-ontologica-de-skills']
    if len(hits)!=1 or str(hits[0].get('versao')) not in ('1.0.5','None') and str(hits[0].get('versao_minima'))!='1.0.5': fail('competencias-governance')
    m=yaml.safe_load((ROOT/'manifesto.yaml').read_text(encoding='utf-8'))
    ents={int(e['id']):e for e in m.get('entradas',[]) if str(e.get('id','')).isdigit()}
    for i in (1562,1563):
        if ents.get(i,{}).get('status')!='aceito': fail('manifest-entry:'+str(i))
    print('CLOUDIFF_T037_MAIN_LINE_RECONCILIATION=PASS')
if __name__=='__main__': main()
