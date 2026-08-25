#!/usr/bin/env bash
set -euo pipefail
NAME="${CLOUDIFF_CADVISOR_NAME:-cloudif-cadvisor}"
IMAGE="${CLOUDIFF_CADVISOR_IMAGE:-ghcr.io/google/cadvisor:v0.57.0}"
EXPECTED_IMAGE_ID="${CLOUDIFF_CADVISOR_IMAGE_ID:-sha256:e75bdb03b74b0b6995f208f166fead2e6e555dde73e44200113bb26f41b1981d}"
IMAGE_TAR="${CLOUDIFF_CADVISOR_IMAGE_TAR:-}"
HOST_IP="127.0.0.1"
HOST_PORT="18081"
CREATED=0
fail(){ echo "STANDARD_MONITORING=FAIL reason=$1" >&2; exit "${2:-1}"; }
cleanup(){ rc=$?; if [[ $rc -ne 0 && $CREATED -eq 1 ]];then docker rm -f "$NAME" >/dev/null 2>&1 || true;fi;exit "$rc"; }
trap cleanup EXIT
[[ ${EUID:-$(id -u)} -eq 0 ]] || fail root-required 10
command -v docker >/dev/null 2>&1 || fail docker-missing 11
systemctl is-active --quiet docker || fail docker-not-active 12
if ! docker image inspect "$IMAGE" >/dev/null 2>&1;then
  [[ -n "$IMAGE_TAR" && -f "$IMAGE_TAR" ]] || fail cadvisor-image-missing 13
  case "$IMAGE_TAR" in
    *.gz|*.tgz) gzip -dc "$IMAGE_TAR" | docker load >/dev/null ;;
    *) docker load -i "$IMAGE_TAR" >/dev/null ;;
  esac
fi
IMAGE_ID=$(docker image inspect "$IMAGE" --format '{{.Id}}')
[[ "$IMAGE_ID" == "$EXPECTED_IMAGE_ID" ]] || fail cadvisor-image-id-mismatch 14
if docker inspect "$NAME" >/dev/null 2>&1;then
  actual=$(docker inspect "$NAME" --format '{{.Config.Image}}|{{.Image}}|{{.HostConfig.NetworkMode}}|{{.HostConfig.Privileged}}|{{.HostConfig.ReadonlyRootfs}}|{{.HostConfig.RestartPolicy.Name}}|{{json .HostConfig.PortBindings}}')
  expected="$IMAGE|$EXPECTED_IMAGE_ID|bridge|true|false|unless-stopped|{\"8080/tcp\":[{\"HostIp\":\"127.0.0.1\",\"HostPort\":\"18081\"}]}"
  [[ "$actual" == "$expected" ]] || fail existing-container-drift 20
else
  docker run -d --name "$NAME" --restart unless-stopped --privileged \
    --security-opt label=disable \
    --device /dev/kmsg:/dev/kmsg \
    -p "$HOST_IP:$HOST_PORT:8080" \
    -v /:/rootfs:ro \
    -v /sys:/sys:ro \
    -v /var/lib/docker:/var/lib/docker:ro \
    -v /var/run:/var/run:ro \
    -v /dev/disk:/dev/disk:ro \
    "$IMAGE" >/dev/null
  CREATED=1
fi
for _ in $(seq 1 30);do
  if curl -fsS --connect-timeout 1 --max-time 2 "http://$HOST_IP:$HOST_PORT/api/v1.3/machine" >/tmp/cloudiff-cadvisor-machine.$$ 2>/dev/null;then break;fi
  sleep 1
done
[[ -s /tmp/cloudiff-cadvisor-machine.$$ ]] || fail cadvisor-api-unavailable 21
python3 - /tmp/cloudiff-cadvisor-machine.$$ <<'PY'
import json,sys
x=json.load(open(sys.argv[1]));assert int(x.get('num_cores',0))>=1
print('CADVISOR_API=PASS cores='+str(x['num_cores']))
PY
rm -f /tmp/cloudiff-cadvisor-machine.$$
[[ "$(docker inspect "$NAME" --format '{{.State.Running}}')" == true ]] || fail cadvisor-not-running 22
binding=$(docker port "$NAME" 8080/tcp)
[[ "$binding" == "127.0.0.1:$HOST_PORT" ]] || fail cadvisor-not-loopback 23
CREATED=0
trap - EXIT
echo "STANDARD_MONITORING=PASS name=$NAME image=$IMAGE image_id=$IMAGE_ID endpoint=http://127.0.0.1:$HOST_PORT"
