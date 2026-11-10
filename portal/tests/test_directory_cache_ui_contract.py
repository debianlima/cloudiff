from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
ACL=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_project_acl_module.py').read_text()
PORTAL=(ROOT/'components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
AD=(ROOT/'components/control-plane/srv/cloudif/lib/cloudif_ad_directory_module.py').read_text()
UNIT=(ROOT/'components/control-plane/etc/systemd/system/cloudif-portal-directory-sync.service').read_text()
TIMER=(ROOT/'components/control-plane/etc/systemd/system/cloudif-portal-directory-sync.timer').read_text()
DROPIN=(ROOT/'components/control-plane/etc/systemd/system/cloudif-admin-portal.service.d/50-directory-cache.conf').read_text()

class DirectoryCacheUiContractTests(unittest.TestCase):
    def test_picker_lists_cached_identities_and_supports_manual_refresh(self):
        for marker in ('Atualizar lista de usuários','acl-directory-pagination','api/directory-sync','api/directory-status','page_size", "50"','cloudifOpenAcl','cloudifAclDirectoryLoaders'):
            self.assertIn(marker,ACL)
        self.assertIn('api/ad-search',ACL)

    def test_only_cloudiff_admin_users_receive_visual_badge(self):
        self.assertIn('x.is_admin === true',ACL)
        self.assertIn('Administrador CloudIFF',ACL)
        self.assertIn('acl-result-item.is-admin',ACL)
        self.assertNotIn('Professor CloudIFF</span>',ACL)

    def test_sync_api_is_project_authorized_and_csrf_protected(self):
        self.assertIn('/cloudiff/portal/api/directory-sync',PORTAL)
        self.assertIn('directory.can_manage_project(user, slug)',PORTAL)
        self.assertIn('_prod_csrf_equal(provided, _prod_csrf_token(user))',PORTAL)
        self.assertIn('_cloudif_security_valid_origin',PORTAL)

    def test_interactive_search_uses_cache_and_short_ad_agent_fallback(self):
        self.assertIn('_cache_module().search',AD)
        self.assertIn('ad_agent_search(q, stype, timeout=2.5)',AD)
        self.assertIn('CLOUDIF_DIRECTORY_LEGACY_FALLBACK',AD)
        self.assertIn('legacy_fallback_enabled',AD)
        self.assertIn('start_sync_background',AD)

    def test_systemd_sync_is_periodic_and_secret_is_external(self):
        self.assertIn('/srv/cloudif/lib/cloudif_directory_cache.py sync',UNIT)
        self.assertIn('EnvironmentFile=/etc/cloudif/portal-directory.env',UNIT)
        self.assertIn('OnUnitActiveSec=10min',TIMER)
        self.assertIn('Persistent=true',TIMER)
        self.assertIn('EnvironmentFile=-/etc/cloudif/portal-directory.env',DROPIN)
        self.assertNotIn('CLOUDIF_DIRECTORY_AUTHENTIK_TOKEN=',UNIT+TIMER+DROPIN)

if __name__=='__main__': unittest.main()
