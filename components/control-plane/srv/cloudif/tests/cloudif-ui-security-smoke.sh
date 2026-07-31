#!/usr/bin/env bash
set -euo pipefail
base=http://10.62.92.7:18094/cloudif/portal/
pass(){ echo "PASS|$1"; }
fail(){ echo "FAIL|$1"; exit 1; }
probe(){ u=$1; g=$2; q=$3; out=$4; curl -sS --max-time 15 -H "X-authentik-username: $u" -H "X-authentik-groups: $g" -D "$out.h" -o "$out.b" "$base$q"; }
probe aluno1 CloudIF-Tenants '?tab=resumo' /tmp/aluno
grep -q 'Aluno' /tmp/aluno.b && pass 'perfil aluno' || fail 'perfil aluno'
! grep -q '>Administração<' /tmp/aluno.b && pass 'admin oculto para aluno' || fail 'admin visível para aluno'
code=$(curl -sS --max-time 15 -H 'X-authentik-username: aluno1' -H 'X-authentik-groups: CloudIF-Tenants' -o /tmp/deny -w '%{http_code}' "$base?tab=admin")
[ "$code" = 403 ] && pass 'admin bloqueado para aluno' || fail 'admin não bloqueado'
probe prof1 'CloudIF-Tenants|CloudIF-Professor' '?tab=resumo' /tmp/prof
grep -q 'Professor' /tmp/prof.b && pass 'perfil professor' || fail 'perfil professor'
! grep -q '>Administração<' /tmp/prof.b && pass 'admin oculto para professor' || fail 'admin visível para professor'
probe admin1 'CloudIF-Tenants|CloudIF-Professor|CloudIF-Tenants-Admin' '?tab=admin' /tmp/admin
grep -q '>Administração<' /tmp/admin.b && pass 'admin visível para administrador' || fail 'admin ausente'
for h in 'X-Frame-Options: DENY' 'Cross-Origin-Opener-Policy: same-origin' 'Cross-Origin-Resource-Policy: same-origin' 'Origin-Agent-Cluster: ?1' 'Content-Security-Policy:'; do grep -Fqi "$h" /tmp/aluno.h && pass "$h" || fail "$h"; done
grep -q 'Pular para o conteúdo principal' /tmp/aluno.b && pass 'skip link' || fail 'skip link'
grep -q 'aria-label="Sair do CloudIF"' /tmp/aluno.b && pass 'logout acessível' || fail 'logout acessível'
echo 'PASS|suite_complete'
