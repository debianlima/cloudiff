import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
REGISTRY=ROOT/'docs/prompts/cloudiff-prompt-registry.json'
CATALOG=ROOT/'docs/PROMPTS-PGH-CLOUDIFF-20261122.md'
AGENTS=ROOT/'docs/PGH-AGENTES-CLOUDIFF.md'
ATLAS=ROOT/'docs/ATLAS-CLOUDIFF-PGH-OPERACAO.md'

class PromptAuthorityCatalogTests(unittest.TestCase):
    def test_registry_has_required_operator_sources(self):
        data=json.loads(REGISTRY.read_text())
        names={x.get('name') for x in data.get('prompts',[])}
        self.assertIn('Meu-Terminal-Oracle-Instrucoes-PGH-1.2.0.md',names)
        self.assertIn('Prompt-Mantenedor-PGH-1.2.0.md',names)
        self.assertIn('PGH-DWP-Agent-Instructions.txt',names)
        self.assertFalse(data.get('secrets_included'))

    def test_dwp_remains_non_authoritative_until_formal_accept(self):
        data=json.loads(REGISTRY.read_text())
        dwp=next(x for x in data['prompts'] if x.get('name')=='PGH-DWP-Agent-Instructions.txt')
        self.assertEqual(dwp.get('status'),'PROPOSED')
        self.assertEqual(dwp.get('version'),'0.1.0')
        self.assertEqual(dwp.get('authority'),'NONE_UNTIL_FORMAL_ACCEPT')
        self.assertEqual(data.get('dwp_state'),'DWP_NOT_ACTIVE')

    def test_human_docs_reference_catalog_and_secret_rule(self):
        catalog=CATALOG.read_text()
        self.assertIn('Segredos deliberadamente omitidos',catalog)
        self.assertIn('DWP_NOT_ACTIVE',catalog)
        self.assertIn('Meu-Terminal-Oracle-Instrucoes-PGH-1.2.0.md',catalog)
        self.assertIn('Prompt-Mantenedor-PGH-1.2.0.md',catalog)
        self.assertIn('PROMPTS-PGH-CLOUDIFF-20261122.md',AGENTS.read_text())
        self.assertIn('PROMPTS-PGH-CLOUDIFF-20261122.md',ATLAS.read_text())

if __name__=='__main__':unittest.main()
