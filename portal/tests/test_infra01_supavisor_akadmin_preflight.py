"""Akadmin Supavisor readiness guard: offline contract and synthetic shell tests."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import yaml

ROOT=Path(__file__).resolve().parents[2]
COMPOSE=ROOT/'tenant-templates/srv/cloudif/tenants/akadmin/docker-compose.yml'

class AkadminSupavisorStartup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.yaml=yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))
        cls.service=cls.yaml['services']['supavisor']
        cls.cmd=cls.service['command'][2]
        cls.shell=cls.cmd.replace('$$','$')  # Compose interpolates $$ to $ at runtime
        cls.prefix=cls.shell.split('/app/bin/migrate',1)[0]

    def test_services_and_backend_port_remain_dynamic(self):
        self.assertEqual(self.service['command'][:2],['/bin/sh','-c'])
        self.assertIn('POSTGRES_HOST',self.service['environment'])
        self.assertIn('POSTGRES_PORT',self.service['environment'])
        self.assertIn('"$POSTGRES_HOST"',self.prefix)
        self.assertIn('"$POSTGRES_PORT"',self.prefix)
        self.assertNotIn('5432',self.prefix)
        self.assertEqual(self.service['depends_on']['db']['condition'],'service_healthy')

    def test_existing_app_chain_preserved(self):
        self.assertIn('/app/bin/migrate && /app/bin/supavisor eval "$(cat /etc/pooler/pooler.exs)" && exec /app/bin/server',self.shell)
        self.assertEqual(self.service['restart'],'unless-stopped')

    def test_bounded_preflight_without_credentials(self):
        self.assertIn('attempt=$((attempt+1))',self.prefix)
        self.assertIn('"$attempt" -ge 12',self.prefix)
        self.assertIn('sleep 2',self.prefix)
        self.assertIn('getent hosts',self.prefix)
        self.assertIn('pg_isready',self.prefix)
        self.assertNotIn('POSTGRES_PASSWORD',self.prefix)
        self.assertNotIn('DATABASE_URL',self.prefix)

    def test_shell_syntax(self):
        run=subprocess.run(['/bin/sh','-n','-c',self.shell],capture_output=True)
        self.assertEqual(run.returncode,0,run.stderr.decode('utf-8','replace')[:100])

    def _simulate(self,dns_ok,pg_ok):
        with tempfile.TemporaryDirectory() as tmp:
            for command,success in (('getent',dns_ok),('pg_isready',pg_ok),('sleep',True)):
                p=Path(tmp)/command
                p.write_text('#!/bin/sh\nexit '+('0' if success else '1')+'\n')
                p.chmod(0o755)
            env={**os.environ,'PATH':tmp+os.pathsep+os.environ.get('PATH',''),
                 'POSTGRES_HOST':'db','POSTGRES_PORT':'54330'}
            run=subprocess.run(['/bin/sh','-c',self.prefix+'printf PREFLIGHT_PASS'],
                               env=env,capture_output=True,text=True,timeout=6)
            return run

    def test_preflight_success_when_dns_and_tcp_ready(self):
        x=self._simulate(True,True)
        self.assertEqual(x.returncode,0)
        self.assertEqual(x.stdout,'PREFLIGHT_PASS')

    def test_preflight_fails_closed_without_dns(self):
        x=self._simulate(False,True)
        self.assertNotEqual(x.returncode,0)
        self.assertEqual(x.stdout,'')
        self.assertIn('bounded retry',x.stderr)

    def test_preflight_fails_closed_without_db_tcp(self):
        x=self._simulate(True,False)
        self.assertNotEqual(x.returncode,0)
        self.assertEqual(x.stdout,'')
        self.assertIn('bounded retry',x.stderr)

if __name__=='__main__': unittest.main()
