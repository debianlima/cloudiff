import unittest
from pathlib import Path

class RuntimeFrameworkInspectionContractTest(unittest.TestCase):
    def test_agent_uses_fixed_read_only_probes(self):
        root=Path(__file__).resolve().parents[2]
        agent=root/'components/runtime/current-apps/komodo-agent-current/cloudif-komodo-agent.py'
        if not agent.exists(): self.skipTest('runtime source is outside isolated Portal release')
        source=agent.read_text()
        self.assertIn('def cloudif_project_runtime_inspect',source)
        self.assertIn('/komodo/project/runtime-inspect',source)
        for command in ("['node','--version']","['npm','--version']","['php','--version']","['nginx','-v']","['apache2','-v']"):
            self.assertIn(command,source)
        section=source[source.index('def cloudif_project_runtime_inspect'):source.index('def cloudif_project_audit')]
        self.assertIn("'read_only':True",section)
        self.assertIn("'mutation_supported':False",section)
        self.assertNotIn('shell=True',section)

if __name__=='__main__':unittest.main()
