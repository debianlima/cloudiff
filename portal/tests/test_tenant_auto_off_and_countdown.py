from pathlib import Path
import unittest
class TenantAutoOffCountdownTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.source=Path('components/control-plane/current-apps/portal-current/cloudif-admin-portal-base.py').read_text()
 def test_final_handler_supports_auto_off_and_timed(self):
  self.assertIn("'always_off','keepalive'",self.source)
  self.assertIn("until=(now+datetime.timedelta(hours=1))",self.source)
  self.assertIn("hours=min(max(int(val('hours')",self.source)
 def test_auto_off_policy_has_real_deadline(self):
  self.assertIn("Desligamento automático agendado para 1 hora",self.source)
  self.assertIn('keepalive_until=excluded.keepalive_until',self.source)
 def test_countdown_is_rendered(self):
  self.assertIn('class=\"db96-countdown\"',self.source)
  self.assertIn('def remaining_text(value):',self.source)
  self.assertIn("return f'{hours:02d}:{minutes:02d}:{seconds:02d}'",self.source)
 def test_ui_explains_janitor_interval(self):
  self.assertIn('janitor verifica a cada 5 minutos',self.source)
if __name__=='__main__':unittest.main()
