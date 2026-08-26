#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
installer_path = root / 'deploy/install_standard_monitoring.sh'
assert installer_path.is_file(), installer_path
installer = installer_path.read_text()

# Supply-chain pin: Faro must not silently float to a different cAdvisor build.
assert 'ghcr.io/google/cadvisor:v0.57.0' in installer
assert 'sha256:e75bdb03b74b0b6995f208f166fead2e6e555dde73e44200113bb26f41b1981d' in installer
assert '[[ "$IMAGE_ID" == "$EXPECTED_IMAGE_ID" ]] || fail cadvisor-image-id-mismatch 14' in installer

# Exposure contract: host telemetry remains local-only unless an explicit later
# architecture change is reviewed and this test is intentionally updated.
assert 'HOST_IP="127.0.0.1"' in installer
assert 'HOST_PORT="18081"' in installer
assert '-p "$HOST_IP:$HOST_PORT:8080"' in installer
assert '[[ "$binding" == "127.0.0.1:$HOST_PORT" ]] || fail cadvisor-not-loopback 23' in installer
assert '0.0.0.0:18081' not in installer

# Idempotency/drift: an existing compliant container is kept; a divergent one
# is rejected instead of being silently mutated.
assert 'if docker inspect "$NAME" >/dev/null 2>&1;then' in installer
assert 'expected="$IMAGE|$EXPECTED_IMAGE_ID|bridge|true|false|unless-stopped|' in installer
assert '[[ "$actual" == "$expected" ]] || fail existing-container-drift 20' in installer

# Readiness must be based on the actual cAdvisor API and running/binding state.
assert 'http://$HOST_IP:$HOST_PORT/api/v1.3/machine' in installer
assert "assert int(x.get('num_cores',0))>=1" in installer
assert "{{.State.Running}}" in installer
assert 'cadvisor-api-unavailable 21' in installer
assert 'cadvisor-not-running 22' in installer

# Installing host monitoring must not manage/restart the CloudIFF agent itself.
for forbidden in (
    'systemctl restart cloudiff-agent',
    'systemctl stop cloudiff-agent',
    'pkill cloudiff-agent',
    'killall cloudiff-agent',
    'docker restart cloudiff-agent',
    'docker rm -f cloudiff-agent',
):
    assert forbidden not in installer, forbidden

print('FARO_STANDARD_MONITORING_CONTRACT=PASS version=v0.57.0 pin=image-id exposure=loopback:18081 drift=fail-closed readiness=api agent=untouched')
