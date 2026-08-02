#!/usr/bin/env python3
import signal,time
from cloudif_portal_publications import claim_next_job,run_job
running=True
def stop(*_):
 global running;running=False
signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
while running:
 job=claim_next_job()
 if job:run_job(job)
 else:time.sleep(2)
