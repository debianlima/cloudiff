from __future__ import annotations
import hashlib
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
EXECUTOR=ROOT/'components/runtime/current-apps/multiservice-deployment-executor-current/cloudif-multiservice-deployment-executor.py'
BROKER=ROOT/'components/control-plane/current-apps/deployment-broker-current/cloudif-deployment-broker.py'
PORTAL=ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py'
KOMODO=ROOT/'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py'


def load_executor():
    td=tempfile.TemporaryDirectory()
    keys=('CLOUDIF_MULTISERVICE_DEPLOYMENT_EXECUTOR_TOKEN','CLOUDIF_MULTISERVICE_DEPLOYMENT_EXECUTOR_DB','CLOUDIF_MULTISERVICE_DEPLOYMENT_RUN_DIR')
    old={k:os.environ.get(k) for k in keys}
    os.environ['CLOUDIF_MULTISERVICE_DEPLOYMENT_EXECUTOR_TOKEN']='test-token'
    os.environ['CLOUDIF_MULTISERVICE_DEPLOYMENT_EXECUTOR_DB']=str(Path(td.name)/'deploy.db')
    os.environ['CLOUDIF_MULTISERVICE_DEPLOYMENT_RUN_DIR']=str(Path(td.name)/'run')
    try:
        name='promotion_executor_'+Path(td.name).name.replace('-','_')
        spec=importlib.util.spec_from_file_location(name,EXECUTOR)
        m=importlib.util.module_from_spec(spec);assert spec.loader;spec.loader.exec_module(m)
    finally:
        for k,v in old.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
    m._test_tmp=td;m.init_db();return m


def load_broker():
    fake=types.ModuleType('cloudif_release_manager')
    fake.project_setting=lambda slug:{'tenant':'tenant-'+slug}
    sys.modules['cloudif_release_manager']=fake
    name='promotion_broker_contract'
    spec=importlib.util.spec_from_file_location(name,BROKER)
    m=importlib.util.module_from_spec(spec);assert spec.loader;spec.loader.exec_module(m)
    return m


class ComposePromotionContractTests(unittest.TestCase):
    def test_broker_plan_is_side_effect_free_and_same_instance_only(self):
        b=load_broker();dep='dep_'+'1'*24;snap='snap_'+'2'*24;digest='3'*64
        def executor(method,path,payload=None,timeout=0):
            if path.startswith('/v1/deployments/'):
                return 200,{'ok':True,'project_slug':'demo','environment':'homologation','status':'running','snapshot_id':snap,'build_plan_digest':digest}
            if path.startswith('/v1/compose-snapshots/'):
                return 200,{'ok':True,'project_slug':'demo','snapshot_id':snap,'snapshot_digest':digest,'source_commit':'4'*40,'status':'ready'}
            raise AssertionError(path)
        with patch.object(b,'_deployment_executor_call',side_effect=executor):
            plan=b._compose_promotion_plan({'project_slug':'demo','deployment_id':dep,'snapshot_id':snap,'snapshot_digest':digest,'trace_id':'trace-promote'})
        self.assertTrue(plan['execution_allowed'],plan['blockers'])
        self.assertEqual(plan['blockers'],[])
        self.assertTrue(plan['side_effect_free'])
        self.assertTrue(plan['sameDeploymentRequired'])
        self.assertTrue(plan['containerRecreationForbidden'])
        self.assertEqual(plan['operation']['action'],'deployment.compose-snapshot.promote-in-place')
        self.assertRegex(plan['promotion_plan_digest'],r'^[a-f0-9]{64}$')

    def test_broker_plan_blocks_identity_mismatch(self):
        b=load_broker();dep='dep_'+'1'*24;snap='snap_'+'2'*24;digest='3'*64
        def executor(method,path,payload=None,timeout=0):
            if path.startswith('/v1/deployments/'):
                return 200,{'ok':True,'project_slug':'demo','environment':'homologation','status':'running','snapshot_id':'snap_'+'9'*24,'build_plan_digest':digest}
            if path.startswith('/v1/compose-snapshots/'):
                return 200,{'ok':True,'project_slug':'demo','snapshot_id':snap,'snapshot_digest':digest,'source_commit':'4'*40,'status':'ready'}
            raise AssertionError(path)
        with patch.object(b,'_deployment_executor_call',side_effect=executor):
            plan=b._compose_promotion_plan({'project_slug':'demo','deployment_id':dep,'snapshot_id':snap,'snapshot_digest':digest,'trace_id':'trace-promote'})
        self.assertFalse(plan['execution_allowed'])
        self.assertIn('homologation-snapshot-mismatch',plan['blockers'])

    def test_executor_promotes_same_deployment_without_recreating_containers(self):
        m=load_executor();dep='dep_'+'1'*24;snap='snap_'+'2'*24;digest='3'*64;container='cloudif-dep-'+'1'*24+'-app'
        con=m.db()
        con.execute("""insert into deployments(
          deployment_id,project_slug,environment,build_job_id,plan_digest,build_plan_digest,config_revision,config_digest,
          toolchain_digest,archive_sha256,variables_digest,status,services_json,routes_json,error_json,created_at,updated_at,snapshot_id
        ) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (dep,'demo','homologation',snap,'5'*64,digest,1,'6'*64,'7'*64,'8'*64,'9'*64,'running',
         json.dumps([{'service':'app','container_name':container,'container_id':'docker-old'}]),
         json.dumps([{'pathPrefix':'/','service':'app','stripPrefix':False}]),'{}',1,1,snap))
        con.execute("""insert into runtime_states(
          project_slug,environment,deployment_id,status,config_revision,config_digest,toolchain_digest,
          build_environment_digest,runtime_environment_digest,environment_digest,build_job_id,variable_names_json,updated_at
        ) values(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ('demo','homologation',dep,'running',1,'6'*64,'7'*64,'','a'*64,'b'*64,snap,json.dumps({'app':['A']}),1))
        con.execute("""insert into compose_snapshots(snapshot_id,project_slug,source_digest,snapshot_digest,source_commit,edge_service,edge_port,manifest_json,status,created_at)
                    values(?,?,?,?,?,?,?,?,?,?)""",
                    (snap,'demo','c'*64,digest,'4'*40,'app',80,'{}','ready',1))
        con.commit();con.close()
        inspect=[{'Id':'docker-same','State':{'Running':True,'Status':'running','Health':{'Status':'healthy'}}}]
        fake=lambda *args,**kwargs: subprocess.CompletedProcess(args,0,stdout=json.dumps(inspect) if args and args[0]=='inspect' else '',stderr='')
        with patch.object(m,'docker',side_effect=fake):
            first=m.promote_compose_deployment({'project_slug':'demo','deployment_id':dep,'snapshot_id':snap,'snapshot_digest':digest})
            second=m.promote_compose_deployment({'project_slug':'demo','deployment_id':dep,'snapshot_id':snap,'snapshot_digest':digest})
        self.assertFalse(first['containersRecreated']);self.assertTrue(first['sameHomologatedDeployment']);self.assertTrue(first['containerIdsPreserved'])
        self.assertTrue(second['idempotent']);self.assertFalse(second['containersRecreated'])
        con=m.db()
        row=con.execute('select environment,status from deployments where deployment_id=?',(dep,)).fetchone()
        prod=con.execute("select deployment_id,status from runtime_states where project_slug='demo' and environment='production'").fetchone()
        audit=con.execute('select count(*) n from deployment_promotions where deployment_id=?',(dep,)).fetchone()
        con.close()
        self.assertEqual(row['environment'],'production');self.assertEqual(row['status'],'running')
        self.assertEqual(prod['deployment_id'],dep);self.assertEqual(prod['status'],'running')
        self.assertEqual(audit['n'],1)

    def test_direct_snapshot_to_production_is_fail_closed(self):
        m=load_executor()
        payload={'deployment_id':'dep_'+'1'*24,'project_slug':'demo','environment':'production','deployment_plan_digest':'2'*64,
                 'config_revision':1,'config_digest':'3'*64,'toolchain_digest':'4'*64,'routes':[],'variables':{},'variables_digest':hashlib.sha256(m.canonical({})).hexdigest()}
        with self.assertRaises(m.DeploymentError) as ctx:m.deploy_compose_snapshot(payload)
        self.assertEqual(ctx.exception.code,'compose_production_requires_homologation_promotion')

    def test_portal_broker_and_gateway_routes_match(self):
        portal=PORTAL.read_text();broker=BROKER.read_text();gateway=KOMODO.read_text();executor=EXECUTOR.read_text()
        for token in ('/v1/compose-promotion-plan','/v1/compose-promotion-execute'):
            self.assertIn(token,portal);self.assertIn(token,broker)
        for token in ('/v1/compose-deployments/promote','/v1/deployments/deactivate','/v1/publication-bridges/deactivate'):
            self.assertIn(token,broker);self.assertIn(token,executor);self.assertIn("_EXECUTOR_PROXY_PREFIX+'"+token+"'",gateway)


if __name__=='__main__':
    unittest.main()
