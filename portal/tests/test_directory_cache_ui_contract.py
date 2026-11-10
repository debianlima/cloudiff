from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
ACL=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_acl_module.py').read_text()
PORTAL_PATH=ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py'
PORTAL=PORTAL_PATH.read_text()
AD=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_ad_directory_module.py').read_text()
SYNC=(ROOT/'components/control-plane/usr/local/sbin/cloudif-directory-cache-sync.py').read_text()
SERVICE=(ROOT/'components/control-plane/etc/systemd/system/cloudif-directory-cache-sync.service').read_text()
TIMER=(ROOT/'components/control-plane/etc/systemd/system/cloudif-directory-cache-sync.timer').read_text()
INSTALL=(ROOT/'deploy/install_directory_cache_sync.sh').read_text()
SETUP=(ROOT/'deploy/setup_directory_cache_auth.sh').read_text()

class DirectoryCacheUiContractTests(unittest.TestCase):
    def test_picker_opens_controlled_catalog_and_lists_without_query(self):
        for marker in ('Selecionar usuário ou grupo','Buscar no catálogo','Carregar mais','Atualizar lista','page_size',"api/ad-search"):
            self.assertIn(marker,ACL)
        self.assertIn("loadDirectory(search.value.trim(),1,false)",ACL)

    def test_only_cloudiff_admin_users_receive_visual_badge(self):
        self.assertIn('admin=!!x.admin',ACL)
        self.assertIn('Administrador CloudIFF',ACL)
        self.assertIn('acl-result-item.is-admin',ACL)
        self.assertNotIn('Professor CloudIFF</span>',ACL)

    def test_manual_sync_is_async_authorized_csrf_protected_and_polled(self):
        for marker in ('/cloudiff/portal/action/directory-cache-sync','/cloudiff/portal/api/directory-status',
                       'directory.can_manage_project(user, slug)','_prod_csrf_equal(provided,_prod_csrf_token(user))',
                       '_cloudif_security_valid_origin','systemctl","--no-block","start"'):
            self.assertIn(marker,PORTAL)
        self.assertIn("api/directory-status",ACL)
        self.assertIn('pollSync(previousStamp',ACL)
        self.assertIn('Sincronizando com Authentik em segundo plano',ACL)

    def test_sync_handler_is_registered_before_server_main_loop(self):
        self.assertLess(PORTAL.index('# CloudIF v108 directory-cache control API BEGIN'),
                        PORTAL.index('if __name__ == "__main__":'))

    def test_interactive_search_uses_cache_then_short_ad_agent_fallback(self):
        for marker in ('def cache_status','def _v91_cache_results','def _v91_ad_agent_results',
                       'timeout=4','CLOUDIF_DIRECTORY_LEGACY_FALLBACK','authentik-cache','ad-agent-live'):
            self.assertIn(marker,AD)

    def test_sync_uses_atomic_db_and_encrypted_external_secret(self):
        self.assertIn('os.replace(tmp, CACHE)',SYNC)
        self.assertIn('PRAGMA integrity_check',SYNC)
        self.assertIn('service_account',SYNC)
        self.assertIn('include_groups',SYNC)
        self.assertIn('LoadCredentialEncrypted=authentik_token:',SERVICE)
        self.assertIn('OnUnitActiveSec=10min',TIMER)
        self.assertIn('Persistent=true',TIMER)
        self.assertIn('systemd-creds encrypt --name=authentik_token -',SETUP)
        for action in ('apply','status','rollback'):
            self.assertIn(action+'()',INSTALL)
        self.assertNotIn('CLOUDIF_DIRECTORY_AUTHENTIK_TOKEN=',SERVICE+TIMER+INSTALL+SETUP)

if __name__=='__main__': unittest.main()
