#!/usr/bin/env bash
set -Eeuo pipefail
TENANT="${1:?tenant}"
/srv/cloudif/bin/cloudif-create-tenant.sh "$TENANT"
