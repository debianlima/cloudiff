#!/usr/bin/env python3
import json,os,subprocess,sys,time,tempfile
from pathlib import Path
LOG=Path('/var/log/cloudif/project-provision.log')
def log(msg):
 LOG.parent.mkdir(parents=True,exist_ok=True)
 with LOG.open('a',encoding='utf-8') as f:f.write(time.strftime('%Y-%m-%dT%H:%M:%S%z')+' '+str(msg)+'\n')
def atomic_job(path,job):
 fd,tmp=tempfile.mkstemp(prefix='.project-job-',dir=str(path.parent))
 try:
  with os.fdopen(fd,'w') as f:json.dump(job,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
  os.chmod(tmp,0o600);os.replace(tmp,path)
 finally:
  try:os.unlink(tmp)
  except FileNotFoundError:pass
def set_state(path,job,status,step='',error='',result=None):
 job['status']=status;job['current_step']=step;job['updated_at']=time.strftime('%Y-%m-%dT%H:%M:%S%z');job['last_error']=error[:500]
 if result is not None:job['result']=result
 atomic_job(path,job)
def run(cmd,timeout=180):
 log('RUN '+' '.join(cmd));p=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
 log(f'RC={p.returncode}');
 if p.stdout:log('STDOUT '+p.stdout[-4000:])
 if p.stderr:log('STDERR '+p.stderr[-4000:])
 return p
def verify_onboarding(slug):
 import sqlite3
 c=sqlite3.connect('/var/lib/cloudif/onboarding/onboarding.db');c.row_factory=sqlite3.Row
 r=c.execute('select status,role_profile,environment from project_onboarding where project_slug=?',(slug,)).fetchone();c.close()
 if not r or r['status']!='ready' or r['role_profile']!='project-admin' or r['environment']!='project':raise RuntimeError('onboarding_not_ready_project_admin')
def main():
 path=Path(sys.argv[1]);job=json.loads(path.read_text());slug=str(job.get('slug') or '')
 set_state(path,job,'running','provision');log(f'START job={path} slug={slug} tenant={job.get("tenant")}')
 try:
  candidates=['/usr/local/sbin/cloudif-project-provision.sh','/usr/local/sbin/cloudif-provision-project.sh']
  found=[c for c in candidates if Path(c).exists() and os.access(c,os.X_OK)]
  if not found:raise RuntimeError('external_provision_script_missing')
  p=run([found[0],str(path)],300)
  if p.returncode:raise RuntimeError('project_provision_failed')
  set_state(path,job,'running','onboarding-reconcile')
  p=run(['/bin/systemctl','start','cloudif-project-onboarding-reconcile.service'],300)
  if p.returncode:raise RuntimeError('onboarding_reconcile_failed')
  verify_onboarding(slug)
  p=run(['/bin/systemctl','start','cloudif-project-capabilities.service'],240)
  if p.returncode:raise RuntimeError('capabilities_reconcile_failed')
  if job.get('template_kind') in ('onboarding','links'):
   set_state(path,job,'running','template')
   p=run(['/usr/local/sbin/cloudif-project-template-apply.py',str(path)],480)
   if p.returncode:raise RuntimeError('template_apply_failed')
   set_state(path,job,'running','initial-publication')
   p=run(['/usr/local/sbin/cloudif-project-initial-publish.py',str(path)],1200)
   if p.returncode:raise RuntimeError('initial_publication_failed')
  set_state(path,job,'succeeded','complete',result={'project_slug':slug,'role_profile':'project-admin','provisioned':True})
  log('SUCCEEDED slug='+slug)
 except Exception as e:
  set_state(path,job,'failed',job.get('current_step') or 'unknown',type(e).__name__+': '+str(e))
  log('FAILED slug='+slug+' '+type(e).__name__+': '+str(e));raise
if __name__=='__main__':main()
