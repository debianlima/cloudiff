#!/usr/bin/env bash
set -Eeuo pipefail
exec /usr/bin/python3 /srv/cloudif/lib/cloudif_project_provision_real.py "$@"
