import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
PANEL_PATH=ROOT/'components/control-plane/current-apps/portal-current/cloudif_db_stage_panel.py'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);assert spec.loader
    sys.modules[name]=mod;spec.loader.exec_module(mod);return mod


PANEL=load('db_stage_panel_t044',PANEL_PATH)


def candidate(stage,number,deps):
    return {'stage_code':stage,'candidate_number':number,
            'runtime_diff_json':json.dumps({'runtimeKind':'multiservice','dependencies':deps})}


class DbStagePanelTests(unittest.TestCase):
    def test_discovers_engines_per_stage_from_recorded_runtime(self):
        cands=[candidate('H1',1,[{'kind':'postgresql','database':'appdb'}]),
               candidate('H2',2,[{'kind':'mysql'},{'kind':'redis'}])]
        rels=[{'stage_code':'P2','candidate_number':2,'runtime_diff_json':cands[1]['runtime_diff_json']}]
        out=PANEL.stage_databases(cands,rels)
        self.assertEqual(out['H1'],[{'engine':'PostgreSQL','kind':'postgresql','database':'appdb'}])
        self.assertEqual([e['engine'] for e in out['H2']],['MySQL','Redis'])
        self.assertEqual([e['engine'] for e in out['P2']],['MySQL','Redis'])

    def test_ignores_non_database_and_malformed_entries(self):
        cands=[candidate('H1',1,[{'kind':'s3','bucket':'x'},{'kind':'postgresql'}]),candidate('H3',3,[])]
        out=PANEL.stage_databases(cands,[])
        self.assertEqual(list(out),['H1'])
        self.assertNotIn('H3',out)
        self.assertEqual(PANEL.stage_databases([{'stage_code':'H9','runtime_diff_json':'{invalid'}],[]),{})

    def test_render_is_read_only_and_escaped(self):
        out=PANEL.stage_databases([candidate('H1',1,[{'kind':'mysql','database':'<script>alert(1)</script>'}])],[])
        html=PANEL.render(out)
        self.assertIn('Banco por estágio',html)
        self.assertIn('H1',html)
        self.assertIn('Somente leitura',html)
        self.assertNotIn('<script>',html)
        self.assertNotIn('3306',html)
        self.assertNotIn('5432',html)

    def test_render_without_evidence_is_honest(self):
        html=PANEL.render({})
        self.assertIn('Nenhum banco embutido detectado',html)
        self.assertIn('Fora do Supabase',html)

    def test_selected_stage_is_marked(self):
        out=PANEL.stage_databases([candidate('H1',1,[{'kind':'postgresql'}])],[])
        self.assertIn('(selecionado)',PANEL.render(out,selected_stage='H1'))


if __name__=='__main__':
    unittest.main()
