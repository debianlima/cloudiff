from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'components/control-plane/usr/local/sbin/cloudif-tenant-guard.py'


def load_module():
    spec=importlib.util.spec_from_file_location('tenant_guard_auto_recovery_test',SOURCE)
    module=importlib.util.module_from_spec(spec);assert spec.loader
    sys.modules[spec.name]=module;spec.loader.exec_module(module);return module


class TenantGuardAutoRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.guard=load_module()

    def test_refresh_does_not_reset_existing_suspect_timer(self):
        decision=self.guard.existing_tenant_recovery_decision(
            'slow','suspect',self.guard.SUSPECT_SECONDS-1,
            current_action='checking',current_message='Aguardando estabilização.',
        )
        self.assertEqual(decision['state'],'suspect')
        self.assertEqual(decision['action'],'checking')
        self.assertFalse(decision['write'])
        self.assertFalse(decision['trigger'])

    def test_suspect_reaches_restore_after_threshold(self):
        decision=self.guard.existing_tenant_recovery_decision(
            'slow','suspect',self.guard.SUSPECT_SECONDS,
            current_action='checking',current_message='Aguardando estabilização.',
        )
        self.assertEqual(decision['state'],'restoring')
        self.assertEqual(decision['action'],'restore')
        self.assertTrue(decision['write'])
        self.assertTrue(decision['trigger'])

    def test_cleanly_stopped_stack_starts_restore_immediately(self):
        decision=self.guard.existing_tenant_recovery_decision('stopped','ready',3600)
        self.assertEqual(decision['state'],'restoring')
        self.assertTrue(decision['write'])
        self.assertTrue(decision['trigger'])
        self.assertIn('parado de forma limpa',decision['message'])

    def test_in_progress_restore_is_not_duplicated(self):
        decision=self.guard.existing_tenant_recovery_decision(
            'stopped','restoring',10,current_action='restore',current_message='Em andamento.'
        )
        self.assertEqual(decision['action'],'restore')
        self.assertFalse(decision['write'])
        self.assertFalse(decision['trigger'])

    def test_compose_classifies_cleanly_stopped_critical_services(self):
        with tempfile.TemporaryDirectory() as temporary:
            tenant='tenant-demo';tdir=Path(temporary)/'tenants'/tenant;tdir.mkdir(parents=True)
            records=[
                {'Service':'db','State':'exited','ExitCode':0,'Health':'healthy'},
                {'Service':'kong','State':'exited','ExitCode':0,'Health':'healthy'},
                {'Service':'studio','State':'exited','ExitCode':143,'Health':'healthy'},
                {'Service':'auth','State':'exited','ExitCode':0,'Health':'healthy'},
            ]
            output='\n'.join(json.dumps(item) for item in records)+'\n'
            old_base=self.guard.BASE;self.guard.BASE=temporary
            try:
                with mock.patch.object(self.guard.subprocess,'check_output',return_value=output):
                    ok,message=self.guard.docker_compose_health(tenant)
            finally:self.guard.BASE=old_base
            self.assertFalse(ok)
            self.assertTrue(message.startswith('STACK_STOPPED_CLEAN:'))

    def test_compose_does_not_call_abnormal_db_exit_clean(self):
        with tempfile.TemporaryDirectory() as temporary:
            tenant='tenant-demo';tdir=Path(temporary)/'tenants'/tenant;tdir.mkdir(parents=True)
            records=[
                {'Service':'db','State':'exited','ExitCode':2},
                {'Service':'kong','State':'exited','ExitCode':0},
                {'Service':'studio','State':'exited','ExitCode':0},
            ]
            output='\n'.join(json.dumps(item) for item in records)+'\n'
            old_base=self.guard.BASE;self.guard.BASE=temporary
            try:
                with mock.patch.object(self.guard.subprocess,'check_output',return_value=output):
                    ok,message=self.guard.docker_compose_health(tenant)
            finally:self.guard.BASE=old_base
            self.assertFalse(ok)
            self.assertFalse(message.startswith('STACK_STOPPED_CLEAN:'))
            self.assertIn('db=exited/exit-2',message)

    def test_tenant_health_promotes_clean_stop_to_stopped_state(self):
        tenant='tenant-demo'
        with tempfile.TemporaryDirectory() as temporary:
            Path(temporary,'tenants',tenant).mkdir(parents=True)
            old_base=self.guard.BASE;self.guard.BASE=temporary;self.guard.HEALTH_CACHE.clear()
            try:
                with mock.patch.object(self.guard,'read_status',return_value={}), \
                     mock.patch.object(self.guard,'docker_compose_health',return_value=(False,'STACK_STOPPED_CLEAN: clean')), \
                     mock.patch.object(self.guard,'kong_port_alive',return_value=(False,'Kong não respondeu')):
                    state,message=self.guard.tenant_health(tenant)
            finally:self.guard.BASE=old_base;self.guard.HEALTH_CACHE.clear()
            self.assertEqual(state,'stopped')
            self.assertIn('STACK_STOPPED_CLEAN',message)

    def test_first_open_warmup_triggers_clean_stop_recovery_without_refresh(self):
        with mock.patch.object(self.guard,'docker_compose_health',return_value=(False,'STACK_STOPPED_CLEAN: clean')), \
             mock.patch.object(self.guard,'read_status',return_value={'STATE':'ready','ACTION':'none','MESSAGE':'','_mtime':0}), \
             mock.patch.object(self.guard,'write_status') as write_status, \
             mock.patch.object(self.guard,'trigger_background') as trigger:
            decision=self.guard.recover_clean_stop_on_open('tenant-demo','alice')
        self.assertTrue(decision['trigger'])
        self.assertEqual(decision['action'],'restore')
        write_status.assert_called_once()
        trigger.assert_called_once_with('tenant-demo','restore','alice')

    def test_first_open_does_not_recover_abnormal_or_partial_stack(self):
        with mock.patch.object(self.guard,'docker_compose_health',return_value=(False,'Estado intermediário ou anormal dos serviços principais: db=exited/exit-2')), \
             mock.patch.object(self.guard,'trigger_background') as trigger:
            decision=self.guard.recover_clean_stop_on_open('tenant-demo','alice')
        self.assertFalse(decision['trigger'])
        trigger.assert_not_called()

    def test_administrative_state_blocks_clean_stop_auto_recovery(self):
        with mock.patch.object(self.guard,'docker_compose_health',return_value=(False,'STACK_STOPPED_CLEAN: clean')), \
             mock.patch.object(self.guard,'read_status',return_value={'STATE':'maintenance','ACTION':'maintenance','MESSAGE':'Janela administrativa','_mtime':0}), \
             mock.patch.object(self.guard,'write_status') as write_status, \
             mock.patch.object(self.guard,'trigger_background') as trigger:
            decision=self.guard.recover_clean_stop_on_open('tenant-demo','alice')
        self.assertFalse(decision['trigger'])
        self.assertEqual(decision['action'],'blocked')
        write_status.assert_not_called();trigger.assert_not_called()

    def test_warmup_handler_calls_clean_stop_recovery_before_returning(self):
        source=SOURCE.read_text()
        start=source.index('if need_warmup_once(tenant, username):')
        end=source.index('health, msg = tenant_health(tenant)',start)
        block=source[start:end]
        self.assertIn('recover_clean_stop_on_open(tenant, username)',block)
        self.assertLess(block.index('recover_clean_stop_on_open'),block.index('self.send_response(403)'))


if __name__=='__main__':unittest.main()
