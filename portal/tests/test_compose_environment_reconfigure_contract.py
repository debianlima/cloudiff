from __future__ import annotations
import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
EXEC=ROOT/'components/runtime/current-apps/multiservice-deployment-executor-current/cloudif-multiservice-deployment-executor.py'
PORTAL=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py'
LAUNCHER=ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal.py'


def load_executor():
    td=tempfile.TemporaryDirectory()
    old={k:os.environ.get(k) for k in ('CLOUDIF_MULTISERVICE_DEPLOYMENT_EXECUTOR_TOKEN','CLOUDIF_MULTISERVICE_DEPLOYMENT_EXECUTOR_DB','CLOUDIF_MULTISERVICE_DEPLOYMENT_RUN_DIR')}
    os.environ['CLOUDIF_MULTISERVICE_DEPLOYMENT_EXECUTOR_TOKEN']='test-token'
    os.environ['CLOUDIF_MULTISERVICE_DEPLOYMENT_EXECUTOR_DB']=str(Path(td.name)/'deploy.db')
    os.environ['CLOUDIF_MULTISERVICE_DEPLOYMENT_RUN_DIR']=str(Path(td.name)/'run')
    try:
        name='env_reconfigure_contract_'+Path(td.name).name.replace('-','_')
        spec=importlib.util.spec_from_file_location(name,EXEC)
        module=importlib.util.module_from_spec(spec);assert spec.loader
        spec.loader.exec_module(module)
    finally:
        for key,value in old.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
    module._test_tmp=td
    module.init_db()
    return module


class ComposeEnvironmentReconfigureContractTests(unittest.TestCase):
    def test_global_variables_apply_to_every_service_and_specific_wins(self):
        m=load_executor()
        variables={'':{'GLOBAL_ONLY':'g','SHARED':'global'},'api':{'SHARED':'api','API_ONLY':'1'},'db':{'DB_ONLY':'1'}}
        self.assertEqual(m._compose_effective_variables(variables,'api'),{'GLOBAL_ONLY':'g','SHARED':'api','API_ONLY':'1'})
        self.assertEqual(m._compose_effective_variables(variables,'db'),{'GLOBAL_ONLY':'g','SHARED':'global','DB_ONLY':'1'})

    def test_regular_multiservice_global_variables_follow_same_semantics(self):
        m=load_executor()
        result=m.normalize_variables({'':{'GLOBAL':'g','SHARED':'global'},'api':{'SHARED':'api'}},{'api','worker'})
        self.assertEqual(result['api'],{'GLOBAL':'g','SHARED':'api'})
        self.assertEqual(result['worker'],{'GLOBAL':'g','SHARED':'global'})

    def test_reconfigure_updates_same_deployment_and_effective_variable_names(self):
        m=load_executor();dep='dep_'+'1'*24;snap='snap_'+'2'*24
        con=m.db()
        con.execute("""insert into deployments(
            deployment_id,project_slug,environment,build_job_id,plan_digest,build_plan_digest,
            config_revision,config_digest,toolchain_digest,archive_sha256,variables_digest,status,
            services_json,routes_json,error_json,created_at,updated_at,snapshot_id
        ) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (dep,'demo','homologation',snap,'3'*64,'4'*64,1,'5'*64,'6'*64,'7'*64,'8'*64,'running',
         json.dumps([{'service':'app','container_name':'cloudif-dep-'+'1'*24+'-app','container_id':'old','variable_names':[]}]),
         json.dumps([{'pathPrefix':'/','service':'app','stripPrefix':False}]),'{}',1,1,snap))
        con.execute("""insert into runtime_states(
            project_slug,environment,deployment_id,status,config_revision,config_digest,toolchain_digest,
            build_environment_digest,runtime_environment_digest,environment_digest,build_job_id,variable_names_json,updated_at
        ) values(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ('demo','homologation',dep,'running',1,'5'*64,'6'*64,'','8'*64,'9'*64,snap,'{}',1))
        con.commit();con.close()
        values={'':{'GLOBAL':'1'}};names={'':['GLOBAL']}
        material={'managed_names_by_service':names,'values_by_service':values}
        digest=hashlib.sha256(m.canonical(material)).hexdigest()
        old_inspect={'Config':{'Env':['BASE=ok']},'HostConfig':{},'NetworkSettings':{'Networks':{}},'Mounts':[],'Image':'sha256:'+'a'*64}
        def fake_docker(*args,**kwargs):
            if args and args[0]=='inspect':return subprocess.CompletedProcess(args,0,stdout=json.dumps([old_inspect]),stderr='')
            return subprocess.CompletedProcess(args,0,stdout='',stderr='')
        payload={'deployment_id':dep,'project_slug':'demo','environment':'homologation','values_by_service':values,
                 'managed_names_by_service':names,'variables_digest':digest,'runtime_environment_digest':'b'*64,
                 'environment_digest':'c'*64,'environment_revision':7}
        with mock.patch.object(m,'docker',side_effect=fake_docker),              mock.patch.object(m,'_compose_reconfigure_create_from_inspect',return_value='newcid'),              mock.patch.object(m,'_compose_container_ready',return_value=(True,'running')),              mock.patch.object(m,'_recover_compose_reconfigure_pair',return_value=None):
            result=m.reconfigure_compose_deployment(payload)
        self.assertTrue(result['deploymentIdentityPreserved'])
        self.assertTrue(result['snapshotPreserved'])
        self.assertTrue(result['volumesPreserved'])
        self.assertTrue(result['containersRecreated'])
        con=m.db()
        row=con.execute('select variables_digest,services_json from deployments where deployment_id=?',(dep,)).fetchone()
        state=con.execute('select variable_names_json,runtime_environment_digest,environment_digest from runtime_states where deployment_id=?',(dep,)).fetchone()
        con.close()
        self.assertEqual(row['variables_digest'],digest)
        self.assertEqual(json.loads(row['services_json'])[0]['container_id'],'newcid')
        self.assertEqual(json.loads(state['variable_names_json']),{'app':['GLOBAL']})
        self.assertEqual(state['runtime_environment_digest'],'b'*64)
        self.assertEqual(state['environment_digest'],'c'*64)

    def test_executor_exposes_standard_reconfigure_route(self):
        src=EXEC.read_text()
        self.assertIn("'/v1/compose-deployments/reconfigure'",src)
        block=src[src.index('def reconfigure_compose_deployment'):src.index('def deploy_compose_snapshot')]
        self.assertIn("docker('rename'",block)
        self.assertIn('recover_interrupted_compose_reconfigurations',src)

    def test_portal_calls_standard_route_with_environment_revision(self):
        src=PORTAL.read_text()
        self.assertIn("/v1/compose-deployments/reconfigure",src)
        self.assertIn("'environment_revision':int(runtime['environmentRevision'])",src)

    def test_portal_launcher_prefers_canonical_library(self):
        src=LAUNCHER.read_text()
        self.assertIn("_CANONICAL_LIB = Path('/srv/cloudif/lib')",src)
        self.assertIn('sys.path.insert(0, canonical)',src)


if __name__=='__main__':
    unittest.main()
