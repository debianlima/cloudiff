#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s portal/tests -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_project_capability_preservation.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_faro_standard_monitoring_contract.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_faro_portal_shadow_contract.py
# Existing production tests are compiled/parsed in CI and executed by the
# production release gate, where the private control-plane network is present.
PYTHONDONTWRITEBYTECODE=1 python3 -c "compile(open('components/control-plane/srv/cloudif/tests/cloudif-ui-security-tests.py').read(), 'cloudif-ui-security-tests.py', 'exec')"
bash -n components/control-plane/srv/cloudif/tests/cloudif-ui-security-smoke.sh
bash -n components/control-plane/srv/cloudif/tests/cloudif-secure-release-gate.sh
