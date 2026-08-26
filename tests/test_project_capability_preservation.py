#!/usr/bin/env python3
from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
schema = json.loads((root / 'contratos/project-capability-preservation.schema.json').read_text())
contract = json.loads((root / 'config/project-capability-contract.json').read_text())

# Regra geral: applications so podem expor capacidades de modo aditivo.
assert schema['title'] == 'ProjectCapabilityPreservation'
assert set(schema['properties']['project_kind']['enum']) == {'application', 'capability'}
application_rule = schema['allOf'][0]['then']['properties']
assert application_rule['capability_mode']['const'] == 'additive'
assert application_rule['algorithm_authority']['const'] == 'source_project'
assert application_rule['delegation']['const'] == 'native_core'
assert application_rule['security_inheritance']['const'] is True
for key in ('required', 'interface_preserved', 'normal_flow_preserved', 'standalone_without_capability_runtime'):
    assert application_rule['native_access']['properties'][key]['const'] is True

# Excecao explicita: um projeto que seja apenas uma competencia nao precisa fingir ser aplicacao.
capability_rule = schema['allOf'][1]['then']['properties']
assert capability_rule['capability_mode']['const'] == 'native_only'

# Instancia CloudIFF: continua aplicacao normal; skills apenas acrescentam acesso.
assert contract['contract_version'] == 1
assert contract['project'] == 'cloudiff'
assert contract['project_kind'] == 'application'
assert contract['capability_mode'] == 'additive'
assert contract['native_access'] == {
    'required': True,
    'interface_preserved': True,
    'normal_flow_preserved': True,
    'standalone_without_capability_runtime': True,
}
assert contract['algorithm_authority'] == 'source_project'
assert contract['delegation'] == 'native_core'
assert contract['security_inheritance'] is True

# O contrato aponta para evidencias reais do projeto, nao para uma implementacao paralela da skill.
for group in ('frozen_interface_contracts', 'native_algorithm_paths'):
    for rel in contract['evidence'][group]:
        assert (root / rel).is_file(), (group, rel)
for key in ('skill_root', 'project_skill_test'):
    assert (root / contract['evidence'][key]).is_file(), key

skill = (root / contract['evidence']['skill_root']).read_text()
assert 'tipo_competencia: projeto' in skill
assert 'FrozenPortalInterface' in skill
assert 'V1 e V2 são um único projeto' in skill
assert 'C/C++ é troca de implementação, não de contrato' in skill

project_gate = (root / contract['evidence']['project_skill_test']).read_text()
assert "delta['frozen_interface']['status']=='master-invariant'" in project_gate
assert "hashlib.sha256(p.read_bytes()).hexdigest()==expected" in project_gate

# Proibicoes minimas que evitam a skill engolir o software de origem.
constraints = '\n'.join(contract['constraints'])
for required in (
    'fluxo nativo',
    'Portal, API, CLI',
    'nucleo autoritativo',
    'autenticacao, autorizacao',
    'application para capability',
):
    assert required in constraints, required

print('PROJECT_CAPABILITY_PRESERVATION=PASS project=cloudiff kind=application mode=additive native_flow=preserved algorithm_authority=source_project')
