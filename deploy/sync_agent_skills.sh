#!/usr/bin/env bash
set -euo pipefail
ACTION=${1:-install}
ARCHIVE=${2:-}
RELEASE=${3:-}
ROOT=/srv/cloudif/agent-skills
validate_archive(){
  [ -f "$ARCHIVE" ];[ -n "$RELEASE" ];[[ "$RELEASE" =~ ^[A-Za-z0-9._-]+$ ]]
  tar -tzf "$ARCHIVE" >/tmp/cloudiff-skills-list.$$;trap 'rm -f /tmp/cloudiff-skills-list.$$' RETURN
  ! grep -Eq '(^/|(^|/)\.\.(/|$))' /tmp/cloudiff-skills-list.$$
  grep -Eq '(^|/)SKILL[.]md$' /tmp/cloudiff-skills-list.$$
}
install_release(){
  validate_archive
  install -d -m 0755 "$ROOT/releases"
  target="$ROOT/releases/$RELEASE";[ ! -e "$target" ]
  tmp="$target.new.$$";install -d -m 0755 "$tmp";tar -xzf "$ARCHIVE" -C "$tmp"
  count=$(find "$tmp" -type f -name SKILL.md | wc -l);[ "$count" -gt 0 ]
  chown -R root:root "$tmp";mv "$tmp" "$target"
  if [ -L "$ROOT/current" ];then ln -sfn "$(readlink -f "$ROOT/current")" "$ROOT/previous";fi
  ln -sfn "$target" "$ROOT/current.new";mv -Tf "$ROOT/current.new" "$ROOT/current"
  echo "AGENT_SKILLS_SYNC=PASS RELEASE=$RELEASE COUNT=$count"
}
case "$ACTION" in install)install_release;;status)readlink -f "$ROOT/current" 2>/dev/null||true;;*)exit 2;;esac
