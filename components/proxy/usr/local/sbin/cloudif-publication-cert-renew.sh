#!/bin/sh
set -eu
docker exec cloudif-nginx-proxy-manager certbot renew --quiet --deploy-hook 'nginx -s reload'
