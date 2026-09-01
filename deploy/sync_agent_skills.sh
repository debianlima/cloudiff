#!/usr/bin/env bash
set -euo pipefail

ACTION=${1:-status}
ARCHIVE=${2:-}
RELEASE=${3:-}
BASELINE_MANIFEST=${4:-}
NEW_MANIFEST=${5:-}
ROOT=${CLOUDIFF_AGENT_SKILLS_ROOT:-/srv/cloudif/agent-skills}
ALLOWED_HOSTS=${CLOUDIFF_AGENT_SKILLS_ALLOWED_HOSTS:-}
OWNER=${CLOUDIFF_AGENT_SKILLS_OWNER:-root:root}

fail(){ echo "AGENT_SKILLS_SYNC=FAIL REASON=$1" >&2; exit "${2:-1}"; }

assert_host_allowed(){
  [ -n "$ALLOWED_HOSTS" ] || fail host_allowlist_missing 20
  local host item ok=0
  host=$(hostname -s)
  IFS=',' read -r -a items <<<"$ALLOWED_HOSTS"
  for item in "${items[@]}"; do [ "$host" = "$item" ] && ok=1; done
  [ "$ok" -eq 1 ] || fail host_not_allowed 21
}

validate_release_name(){ [ -n "$RELEASE" ] && [[ "$RELEASE" =~ ^[A-Za-z0-9._-]+$ ]] || fail invalid_release 22; }

validate_archive(){
  [ -f "$ARCHIVE" ] || fail archive_missing 23
  python3 - "$ARCHIVE" <<'PY'
import pathlib,sys,tarfile
p=pathlib.Path(sys.argv[1])
with tarfile.open(p,'r:gz') as t:
    members=t.getmembers()
    if not members: raise SystemExit('empty archive')
    has_skill=False
    for m in members:
        name=pathlib.PurePosixPath(m.name)
        if name.is_absolute() or '..' in name.parts: raise SystemExit('unsafe archive path')
        if name.name=='SKILL.md': has_skill=True
        if not (m.isfile() or m.isdir()):
            raise SystemExit(f'unsupported archive member: {m.name}')
    if not has_skill: raise SystemExit('SKILL.md missing')
PY
}

manifest_tree(){
  local tree=$1 out=$2 rec mode path
  ( cd "$tree" && find . -type f -printf '%m %p\0' | sort -z | while IFS= read -r -d '' rec; do
      mode=${rec%% *};path=${rec#* }
      printf '%s %s %s\n' "$mode" "$(sha256sum "$path" | awk '{print $1}')" "$path"
    done ) >"$out"
}

validate_manifests(){
  [ -s "$BASELINE_MANIFEST" ] || fail baseline_manifest_missing 24
  [ -s "$NEW_MANIFEST" ] || fail new_manifest_missing 25
  grep -Eq ' (^|.*/)SKILL[.]md$' "$NEW_MANIFEST" || fail new_manifest_without_skill 26
}

assert_current_baseline(){
  local current actual
  [ -L "$ROOT/current" ] || fail current_not_symlink 33
  current=$(readlink -f "$ROOT/current" 2>/dev/null || true)
  [ -n "$current" ] && [ -d "$current" ] || fail current_missing 27
  actual=$(mktemp)
  manifest_tree "$current" "$actual"
  if ! cmp -s "$BASELINE_MANIFEST" "$actual"; then rm -f "$actual"; fail baseline_diverged 28; fi
  rm -f "$actual"
}

validate_extracted(){
  local tree=$1 actual
  actual=$(mktemp)
  manifest_tree "$tree" "$actual"
  if ! cmp -s "$NEW_MANIFEST" "$actual"; then rm -f "$actual"; return 1; fi
  rm -f "$actual"
  return 0
}

extract_candidate(){
  local dir=$1
  install -d -m 0755 "$dir"
  # Service umasks vary by profile (e.g. 077 under hardened MCP workers).
  # Normalize extraction to 022 so the signed mode+hash manifest is deterministic.
  ( umask 022; tar -xzf "$ARCHIVE" -C "$dir" )
  validate_extracted "$dir"
}

validate_archive_manifest(){
  local tmp
  tmp=$(mktemp -d)
  if ! extract_candidate "$tmp"; then rm -rf "$tmp"; fail new_manifest_mismatch 29; fi
  rm -rf "$tmp"
}

dry_run(){
  assert_host_allowed;validate_release_name;validate_archive;validate_manifests;assert_current_baseline
  install -d -m 0755 "$ROOT/releases"
  validate_archive_manifest
  local target tmp
  target="$ROOT/releases/$RELEASE"
  if [ -e "$target" ]; then
    [ -d "$target" ] || fail target_not_directory 30
    validate_extracted "$target" || fail new_manifest_mismatch 29
  else
    tmp=$(mktemp -d "$ROOT/releases/.${RELEASE}.dryrun.XXXXXX")
    if ! extract_candidate "$tmp"; then rm -rf "$tmp"; fail new_manifest_mismatch 29; fi
    rm -rf "$tmp"
  fi
  echo "AGENT_SKILLS_SYNC=DRY_RUN_PASS RELEASE=$RELEASE"
}

install_release(){
  assert_host_allowed;validate_release_name;validate_archive;validate_manifests;assert_current_baseline
  install -d -m 0755 "$ROOT/releases"
  validate_archive_manifest
  local target tmp current count
  target="$ROOT/releases/$RELEASE"
  if [ -e "$target" ]; then
    [ -d "$target" ] || fail target_not_directory 30
    validate_extracted "$target" || fail new_manifest_mismatch 29
  else
    tmp=$(mktemp -d "$ROOT/releases/.${RELEASE}.new.XXXXXX")
    if ! extract_candidate "$tmp"; then rm -rf "$tmp"; fail new_manifest_mismatch 29; fi
    chown -R "$OWNER" "$tmp"
    mv "$tmp" "$target"
  fi
  current=$(readlink -f "$ROOT/current")
  if [ "$current" = "$target" ]; then
    count=$(find "$target" -type f -name SKILL.md | wc -l)
    echo "AGENT_SKILLS_SYNC=NOOP RELEASE=$RELEASE COUNT=$count"
    return 0
  fi
  if [ -e "$ROOT/previous" ] || [ -L "$ROOT/previous" ]; then
    [ -L "$ROOT/previous" ] || fail previous_not_symlink 34
  fi
  ln -sfn "$current" "$ROOT/previous"
  ln -sfn "$target" "$ROOT/current.new"
  mv -Tf "$ROOT/current.new" "$ROOT/current"
  count=$(find "$target" -type f -name SKILL.md | wc -l)
  echo "AGENT_SKILLS_SYNC=PASS RELEASE=$RELEASE COUNT=$count"
}

rollback(){
  assert_host_allowed
  local current previous
  [ -L "$ROOT/current" ] || fail current_not_symlink 33
  [ -L "$ROOT/previous" ] || fail previous_not_symlink 34
  current=$(readlink -f "$ROOT/current" 2>/dev/null || true)
  previous=$(readlink -f "$ROOT/previous" 2>/dev/null || true)
  [ -n "$current" ] && [ -d "$current" ] || fail current_missing 27
  [ -n "$previous" ] && [ -d "$previous" ] || fail previous_missing 31
  [ "$current" != "$previous" ] || fail previous_equals_current 32
  ln -sfn "$previous" "$ROOT/current.new"
  mv -Tf "$ROOT/current.new" "$ROOT/current"
  ln -sfn "$current" "$ROOT/previous.new"
  mv -Tf "$ROOT/previous.new" "$ROOT/previous"
  echo "AGENT_SKILLS_SYNC=ROLLBACK_PASS CURRENT=$(basename "$previous") PREVIOUS=$(basename "$current")"
}

status(){
  printf 'CURRENT=';readlink -f "$ROOT/current" 2>/dev/null || true
  printf 'PREVIOUS=';readlink -f "$ROOT/previous" 2>/dev/null || true
  local current
  current=$(readlink -f "$ROOT/current" 2>/dev/null || true)
  if [ -d "$current" ]; then printf 'COUNT=';find "$current" -type f -name SKILL.md | wc -l; fi
}

case "$ACTION" in
  dry-run) dry_run ;;
  install) install_release ;;
  rollback) rollback ;;
  status) status ;;
  *) fail invalid_action 2 ;;
esac
