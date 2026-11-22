#!/usr/bin/env python3
import fcntl,os,signal,time
from cloudif_portal_publications import claim_next_job,run_job
LOCK='/run/cloudif/portal-publication-lifecycle.lock'
running=True
def stop(*_):
 global running;running=False
def acquire():
 os.makedirs(os.path.dirname(LOCK),exist_ok=True);fd=os.open(LOCK,os.O_CREAT|os.O_RDWR,0o600);fcntl.flock(fd,fcntl.LOCK_EX);return fd
def release(fd):
 try:fcntl.flock(fd,fcntl.LOCK_UN)
 finally:os.close(fd)
signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
while running:
 fd=acquire()
 try:
  job=claim_next_job()
  if job:run_job(job)
 finally:release(fd)
 if not job:time.sleep(2)
