#!/bin/sh
set -eu
getent group cloudif-remote >/dev/null 2>&1 || groupadd --system cloudif-remote
getent passwd cloudif-authz >/dev/null 2>&1 || useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin cloudif-authz
for n in $(seq -w 1 256); do
  u="cifremote$n"
  getent passwd "$u" >/dev/null 2>&1 || useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin --gid cloudif-remote "$u"
  # Accounts must be unlocked for OpenSSH public-key auth; password auth is disabled in sshd.
  pass=$(openssl rand -hex 24)
  hash=$(openssl passwd -6 "$pass")
  usermod -p "$hash" "$u"
  unset pass hash
done
# Machine connector: remote-forward only; actual limits are enforced by sshd Match block.
if ! getent passwd cifconn-hosp >/dev/null 2>&1; then
  useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin --gid cloudif-remote cifconn-hosp
fi
pass=$(openssl rand -hex 24); hash=$(openssl passwd -6 "$pass"); usermod -p "$hash" cifconn-hosp; unset pass hash
exit 0
