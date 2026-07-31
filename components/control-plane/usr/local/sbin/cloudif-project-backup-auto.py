#!/usr/bin/env python3
import subprocess,sys
r=subprocess.run(['/usr/local/sbin/cloudif-project-backup.py','run-enabled'])
sys.exit(r.returncode)
