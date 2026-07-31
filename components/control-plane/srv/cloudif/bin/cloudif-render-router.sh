#!/usr/bin/env bash
set -Eeuo pipefail

echo "AVISO: cloudif-render-router.sh foi substituído por wrapper."
echo "Render oficial atual: /srv/cloudif/bin/cloudif-render-router-sso.sh"
echo "Chamando render oficial..."

exec "/srv/cloudif/bin/cloudif-render-router-sso.sh" "$@"
