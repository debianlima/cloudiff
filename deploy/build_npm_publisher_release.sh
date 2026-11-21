#!/usr/bin/env bash
set -euo pipefail

usage(){ echo "usage: $0 --source DIR --output DIR --source-commit SHA --source-tree SHA" >&2; exit 64; }
SOURCE=''; OUTPUT=''; SOURCE_COMMIT=''; SOURCE_TREE=''
while (($#)); do
  case "$1" in
    --source) SOURCE=${2:-}; shift 2;;
    --output) OUTPUT=${2:-}; shift 2;;
    --source-commit) SOURCE_COMMIT=${2:-}; shift 2;;
    --source-tree) SOURCE_TREE=${2:-}; shift 2;;
    *) usage;;
  esac
done
[[ -d "$SOURCE" && -n "$OUTPUT" && "$SOURCE_COMMIT" =~ ^[a-f0-9]{40}$ && "$SOURCE_TREE" =~ ^[a-f0-9]{40}$ ]] || usage
command -v cmake >/dev/null
command -v ninja >/dev/null
command -v clang++ >/dev/null
command -v readelf >/dev/null
command -v sha256sum >/dev/null

SOURCE=$(readlink -f "$SOURCE")
mkdir -p "$OUTPUT"
OUTPUT=$(readlink -f "$OUTPUT")
BUILD="$OUTPUT/build"
RELEASE="$OUTPUT/release"
rm -rf "$BUILD" "$RELEASE"
mkdir -p "$BUILD" "$RELEASE/bin"

COMPILER=$(clang++ --version | head -n1)
JOBS=${CLOUDIFF_BUILD_JOBS:-2}
[[ "$JOBS" =~ ^[1-4]$ ]] || { echo 'CLOUDIFF_BUILD_JOBS must be 1..4' >&2; exit 64; }
BUILD_COMMAND="cmake -S <source> -B <build> -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=clang++ && nice -n 10 cmake --build <build> --parallel $JOBS --target cloudiff-agent test_npm_publisher_provider && nice -n 10 ctest --test-dir <build> -R '^npm_publisher_provider$' --output-on-failure"
BUILD_COMMAND_DIGEST=$(printf '%s' "$BUILD_COMMAND" | sha256sum | awk '{print $1}')

cmake -S "$SOURCE" -B "$BUILD" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=clang++
nice -n 10 cmake --build "$BUILD" --parallel "$JOBS" --target cloudiff-agent test_npm_publisher_provider
nice -n 10 ctest --test-dir "$BUILD" -R '^npm_publisher_provider$' --output-on-failure

install -m 0755 "$BUILD/cloudiff-agent" "$RELEASE/bin/cloudiff-agent"
BINARY_SHA=$(sha256sum "$RELEASE/bin/cloudiff-agent" | awk '{print $1}')
BUILD_ID=$(readelf -n "$RELEASE/bin/cloudiff-agent" 2>/dev/null | awk '/Build ID:/{print $3;exit}')
[[ "$BINARY_SHA" =~ ^[a-f0-9]{64}$ && "$BUILD_ID" =~ ^[a-f0-9]+$ ]]
BUILT_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)

python3 - "$RELEASE/release-manifest.json" "$SOURCE_COMMIT" "$SOURCE_TREE" "$BINARY_SHA" "$BUILD_ID" "$COMPILER" "$BUILD_COMMAND_DIGEST" "$BUILT_AT" <<'PY'
import json,sys
out,commit,tree,bsha,bid,compiler,cmd,built=sys.argv[1:]
obj={
  'schema':'cloudiff-release-manifest/1',
  'component':'NpmPublisherProvider',
  'source_commit':commit,
  'source_tree':tree,
  'binary_sha256':bsha,
  'gnu_build_id':bid,
  'compiler':compiler,
  'build_profile':'Release',
  'build_command_digest':cmd,
  'built_at':built,
  'tests':{'npm_publisher_provider':'PASS'}
}
with open(out,'w') as f: json.dump(obj,f,indent=2,sort_keys=True);f.write('\n')
PY
printf '%s  %s\n' "$BINARY_SHA" 'bin/cloudiff-agent' > "$RELEASE/SHA256SUMS"
printf '%s\n' "$SOURCE_COMMIT" > "$RELEASE/SOURCE_SHA"
printf 'build_ok=true\nbinary_sha256=%s\ngnu_build_id=%s\nrelease_dir=%s\n' "$BINARY_SHA" "$BUILD_ID" "$RELEASE"
