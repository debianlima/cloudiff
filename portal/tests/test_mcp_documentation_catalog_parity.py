from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MCP=ROOT/'components/control-plane/current-apps/mcp-gateway-current/cloudif-mcp-gateway.py'
GUIDE=ROOT/'components/control-plane/current-apps/portal-current/cloudif_ai_agents_guide.py'
LEGACY=ROOT/'portal/legacy/cloudif_ai_agents_guide.py'

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);assert spec.loader
    sys.modules[name]=module;spec.loader.exec_module(module);return module

class MCPDocumentationCatalogParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mcp=load(MCP,'mcp_documentation_parity_gateway');cls.guide=load(GUIDE,'mcp_documentation_parity_guide')
    def test_every_published_tool_has_complete_documentation(self):
        published={item['name'] for item in self.mcp.TOOLS};documented=set(self.guide.TOOL_DOC)
        self.assertEqual(published,documented)
        self.assertTrue(all(len(self.guide.TOOL_DOC[name])==4 and all(str(value).strip() for value in self.guide.TOOL_DOC[name]) for name in documented))
    def test_scope_guide_exposes_every_documented_tool_with_a_scope(self):
        flattened={tool for tools in self.guide.SCOPE_TOOLS.values() for tool in tools}
        scoped={name for name,scope in self.mcp.SCOPE_BY_TOOL.items() if scope}
        self.assertTrue(scoped <= flattened, sorted(scoped-flattened))
    def test_legacy_guide_remains_byte_compatible(self):
        self.assertEqual(GUIDE.read_bytes(),LEGACY.read_bytes())

if __name__=='__main__':unittest.main()
