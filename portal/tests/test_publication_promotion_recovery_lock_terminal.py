import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PUB=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_publications.py').read_text()
KOMODO=(ROOT/'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py').read_text()
REFRESH=(ROOT/'components/control-plane/usr/local/sbin/cloudif-portal-refresh-cache.py').read_text()
WORKER=(ROOT/'components/control-plane/usr/local/sbin/cloudif-publication-worker.py').read_text()
READMODEL=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_portal_readmodel.py').read_text()

class PublicationPromotionRecoveryTests(unittest.TestCase):
    def test_publication_number_has_atomic_candidate_reservation(self):
        self.assertIn('CREATE TABLE IF NOT EXISTS publication_number_reservations',PUB)
        self.assertIn('def _reserve_publication_number(con,slug,candidate_number,publication_number=None):',PUB)
        self.assertIn("UNIQUE(project_slug,publication_number)",PUB)
        self.assertIn("max(publication_number),0) from publication_number_reservations",PUB)
        self.assertIn("Conflito de nome: P",PUB)
        self.assertIn("publication=_reserve_publication_number(con,slug,int(candidate_number))",PUB)

    def test_compose_promotion_has_name_preflight_and_partial_recovery(self):
        self.assertIn('def _compose_publication_preflight(slug,candidate,publication):',PUB)
        self.assertIn("project_publications where project_slug=? and (version=? or version_hostname=?)",PUB)
        self.assertIn("publication_jobs where project_slug=? and operation='production_release' and publication_number=? and candidate_number<>?",PUB)
        self.assertIn("production_activation_requests where project_slug=? and publication_number=? and candidate_number<>?",PUB)
        self.assertIn("recoveringPartialPromotion",PUB)
        self.assertIn("environment=='production'",PUB)
        self.assertIn("recoveredPartialPromotion",PUB)
        self.assertIn('def _finalize_compose_publication_db(',PUB)

    def test_partial_promotion_job_can_recover_without_stale_environment_digest(self):
        start=PUB.index('def _validate_project_permission_job(')
        end=PUB.index('\ndef enqueue_authorized_publication',start)
        body=PUB[start:end]
        self.assertIn("partial=str(_compose_deployment_status(dep).get('environment') or '')=='production'",body)
        self.assertIn("if not partial and not hmac.compare_digest",body)
        self.assertIn("if partial and not re.fullmatch",body)

    def test_finalizer_waits_and_retries_sqlite_lock(self):
        start=PUB.index('def _finalize_compose_publication_db(')
        end=PUB.index('\ndef _publish_linked_compose_homologated_candidate',start)
        body=PUB[start:end]
        self.assertIn("con=_publication_db(60,True)",body)
        self.assertIn("con.execute('begin immediate')",body)
        self.assertIn("for attempt in range(4):",body)
        self.assertIn("'locked' not in str(exc).lower()",body)
        self.assertIn("status='published'",body)

    def test_readmodel_uses_separate_disposable_sqlite(self):
        self.assertIn("DB='/var/lib/cloudif/portal/cloudif-portal-readmodel.db'",READMODEL)
        self.assertNotIn("DB='/var/lib/cloudif/portal/cloudif-portal.db'",READMODEL)
        self.assertIn('sqlite3.connect(DB,timeout=30)',READMODEL)
        self.assertIn('pragma busy_timeout=30000',READMODEL)

    def test_refresh_and_worker_share_lifecycle_mutex(self):
        self.assertIn('/run/cloudif/portal-publication-lifecycle.lock',REFRESH)
        self.assertIn('LOCK_EX|fcntl.LOCK_NB',REFRESH)
        self.assertIn('DEFERRED: lifecycle de publicação ativo',REFRESH)
        self.assertIn('/run/cloudif/portal-publication-lifecycle.lock',WORKER)
        self.assertIn('fcntl.LOCK_EX',WORKER)
        self.assertIn('job=claim_next_job()',WORKER)
        self.assertIn('if job:run_job(job)',WORKER)

    def test_node_refresh_does_not_hold_db_during_network_fetch(self):
        start=REFRESH.index('def refresh_nodes():')
        end=REFRESH.index('\ndef tenants_registry',start)
        body=REFRESH[start:end]
        self.assertIn('con.close()',body)
        self.assertIn('result=fetch_json(url,15)',body)
        self.assertIn('samples.append(',body)
        self.assertIn('executemany(',body)

    def test_cutover_waits_previous_production_inactive(self):
        self.assertIn('def _wait_deployment_inactive(',PUB)
        self.assertIn("status in {'inactive','removed'}",PUB)
        self.assertIn("_wait_deployment_inactive(previous_dep)",PUB)
        self.assertIn("_wait_deployment_inactive(current_dep)",PUB)

    def test_compose_terminal_uses_deployment_identity(self):
        self.assertIn("payload['deployment_id']=deployment_id",PUB)
        self.assertIn("payload['container_candidates']=deployment_targets['containers']",PUB)
        self.assertIn("terminalSource':'compose_deployment_service'",PUB)
        self.assertIn("label=org.cloudiff.deployment=",KOMODO)
        self.assertIn("labels.get('org.cloudiff.deployment')",KOMODO)
        self.assertIn("labels.get('org.cloudiff.project')",KOMODO)
        self.assertIn("selected_service",KOMODO)
        self.assertIn("'target_mode':'container'",KOMODO)
        self.assertIn("'sameRuntimeAcrossPromotion':True",KOMODO)

if __name__=='__main__':unittest.main()
