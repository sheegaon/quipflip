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

When the installed server LaunchAgent declares an SMTP host, a pre-flight check
verifies the matching SMTP_PASSWORD exists in the Keychain (without printing it)
and aborts an --apply run if it is missing.
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

# SMTP readiness pre-flight. The release reuses the installed server LaunchAgent
# environment, so if it declares an SMTP host the matching SMTP_PASSWORD must
# already live in the Keychain; otherwise magic-link email fails at runtime with
# 503 magic_link_email_failed. Catch that here, before the expensive build, the
# same way the uncommitted-changes guard fails fast only when applying.
SERVER_PLIST="${SERVER_PLIST:-$HOME/Library/LaunchAgents/com.crowdcraft.server.plist}"
PLIST_BUDDY="/usr/libexec/PlistBuddy"
SMTP_STATUS="not checked (no installed server plist)"

plist_env_value() {
  "$PLIST_BUDDY" -c "Print :EnvironmentVariables:$1" "$SERVER_PLIST" 2>/dev/null || true
}

if [[ -x "$PLIST_BUDDY" && -f "$SERVER_PLIST" ]]; then
  SMTP_HOST_CONFIGURED="$(plist_env_value SMTP_HOST)"
  if [[ -n "$SMTP_HOST_CONFIGURED" ]]; then
    SMTP_KEYCHAIN_SERVICE="$(plist_env_value KEYCHAIN_SERVICE)"
    SMTP_KEYCHAIN_SERVICE="${SMTP_KEYCHAIN_SERVICE:-com.crowdcraft.production}"
    SMTP_PASSWORD_ACCOUNT="$(plist_env_value SMTP_PASSWORD_ACCOUNT)"
    SMTP_PASSWORD_ACCOUNT="${SMTP_PASSWORD_ACCOUNT:-SMTP_PASSWORD}"
    # `-w` is omitted so existence is verified without printing the secret.
    if command -v security >/dev/null 2>&1 \
      && security find-generic-password -s "$SMTP_KEYCHAIN_SERVICE" -a "$SMTP_PASSWORD_ACCOUNT" >/dev/null 2>&1; then
      SMTP_STATUS="${SMTP_HOST_CONFIGURED} (Keychain ${SMTP_KEYCHAIN_SERVICE}/${SMTP_PASSWORD_ACCOUNT} present)"
    elif [[ "$APPLY" -eq 1 ]]; then
      echo "❌ Error: SMTP_HOST is set to '${SMTP_HOST_CONFIGURED}' but Keychain item" >&2
      echo "   ${SMTP_KEYCHAIN_SERVICE}/${SMTP_PASSWORD_ACCOUNT} is missing; magic-link email would fail at runtime." >&2
      echo "   Store it first:" >&2
      echo "     ${PYTHON_BIN} scripts/ops/crowdcraft_ops.py secrets keychain-store --with-smtp --skip-secret --skip-openai --skip-gemini --apply" >&2
      exit 1
    else
      SMTP_STATUS="${SMTP_HOST_CONFIGURED} (⚠ Keychain ${SMTP_KEYCHAIN_SERVICE}/${SMTP_PASSWORD_ACCOUNT} missing)"
    fi
  else
    SMTP_STATUS="not configured (magic-link email disabled)"
  fi
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
echo "SMTP: ${SMTP_STATUS}"
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
