#!/usr/bin/env bash
set -Eeuo pipefail
exec /srv/cloudif/bin/cloudif-fast-ensure-tenant.sh "$@"
