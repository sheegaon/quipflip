#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
APPLY=1
SKIP_SMOKE=0
RELEASE_ID=""
REVISION=""

usage() {
  cat <<'EOF'
Usage: scripts/restart-production-server.sh [--dry-run] [--skip-smoke] [--release-id ID] [--revision SHA]

Runs the canonical Crowdcraft release pipeline, which includes the verification
gate and the four frontend builds, then applies the guarded deployment release.
Use --dry-run to print the planned release without mutating production state.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      APPLY=0
      ;;
    --skip-smoke)
      SKIP_SMOKE=1
      ;;
    --release-id)
      if [[ $# -lt 2 ]]; then
        echo "❌ Error: --release-id requires a value" >&2
        usage >&2
        exit 2
      fi
      RELEASE_ID="$2"
      shift
      ;;
    --revision)
      if [[ $# -lt 2 ]]; then
        echo "❌ Error: --revision requires a value" >&2
        usage >&2
        exit 2
      fi
      REVISION="$2"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "❌ Error: Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

cd "$ROOT_DIR"

if [[ "$APPLY" -eq 1 ]] && ! git diff-index --quiet HEAD --; then
  echo "❌ Error: Uncommitted changes detected" >&2
  echo "   Please commit or stash changes before deploying" >&2
  exit 1
fi

if [[ -z "$REVISION" ]]; then
  REVISION="$(git rev-parse HEAD)"
fi

echo "════════════════════════════════════════════════════════════"
echo "🚀 Crowdcraft Production Release"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Revision: ${REVISION}"
echo "Mode: $([[ "$APPLY" -eq 1 ]] && echo apply || echo dry-run)"
if [[ -n "$RELEASE_ID" ]]; then
  echo "Release ID: ${RELEASE_ID}"
fi
if [[ "$SKIP_SMOKE" -eq 1 ]]; then
  echo "Smoke: skipped"
fi
echo ""

DEPLOY_ARGS=(scripts/ops/crowdcraft_ops.py deploy release --revision "$REVISION")
if [[ -n "$RELEASE_ID" ]]; then
  DEPLOY_ARGS+=(--release-id "$RELEASE_ID")
fi
if [[ "$SKIP_SMOKE" -eq 1 ]]; then
  DEPLOY_ARGS+=(--skip-smoke)
fi
if [[ "$APPLY" -eq 1 ]]; then
  DEPLOY_ARGS+=(--apply)
fi

"$PYTHON_BIN" "${DEPLOY_ARGS[@]}"
