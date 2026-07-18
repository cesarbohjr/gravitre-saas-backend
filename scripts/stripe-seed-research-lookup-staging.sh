#!/usr/bin/env bash
# Option A: create research_lookups_used meter + $0.35 price in Stripe TEST mode.
#
# Usage:
#   export STRIPE_SECRET_KEY=sk_test_...
#   bash scripts/stripe-seed-research-lookup-staging.sh
#
# Or pull test key from Railway (requires railway login + STRIPE_SECRET_KEY=sk_test_* on service):
#   bash scripts/stripe-seed-research-lookup-staging.sh --from-railway
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAILWAY_SERVICE="${RAILWAY_SERVICE:-gravitre-saas-backend}"
FROM_RAILWAY=false
PUSH_RAILWAY=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from-railway) FROM_RAILWAY=true; shift ;;
    --push-railway) PUSH_RAILWAY=true; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

load_dotenv() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" =~ ^[[:space:]]*$ ]] && continue
    if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
      local key="${BASH_REMATCH[1]}"
      local val="${BASH_REMATCH[2]}"
      val="${val%\"}"; val="${val#\"}"
      if [[ -z "${!key:-}" ]]; then
        export "$key=$val"
      fi
    fi
  done < "$file"
}

load_dotenv "${REPO_ROOT}/backend/.env.operator.local"
load_dotenv "${REPO_ROOT}/backend/.env"

# Railway CLI accepts RAILWAY_TOKEN for non-interactive auth (project token).
if [[ -n "${RAILWAY_TOKEN:-}" ]]; then
  export RAILWAY_TOKEN
fi

if [[ "$FROM_RAILWAY" == "true" ]]; then
  RAILWAY_BIN="${RAILWAY_BIN:-}"
  if [[ -z "$RAILWAY_BIN" && -x "${HOME}/.railway/bin/railway" ]]; then
    RAILWAY_BIN="${HOME}/.railway/bin/railway"
  elif command -v railway >/dev/null 2>&1; then
    RAILWAY_BIN="railway"
  fi
  if [[ -z "$RAILWAY_BIN" ]]; then
    echo "ERROR: railway CLI not found" >&2
    exit 1
  fi
  if ! "$RAILWAY_BIN" whoami >/dev/null 2>&1; then
    echo "ERROR: railway auth failed — run: railway login OR set RAILWAY_TOKEN (project token)" >&2
    exit 1
  fi
  STRIPE_SECRET_KEY="$("$RAILWAY_BIN" variables --service "$RAILWAY_SERVICE" --json \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('STRIPE_SECRET_KEY','').strip())")"
  export STRIPE_SECRET_KEY
fi

if [[ -z "${STRIPE_SECRET_KEY:-}" ]]; then
  echo "ERROR: STRIPE_SECRET_KEY not set." >&2
  echo "  export STRIPE_SECRET_KEY=sk_test_..." >&2
  echo "  or: bash $0 --from-railway  (requires railway login)" >&2
  exit 1
fi

if [[ "${STRIPE_SECRET_KEY}" != sk_test_* ]]; then
  echo "ERROR: staging script requires sk_test_* key (got prefix: ${STRIPE_SECRET_KEY:0:8}...)" >&2
  echo "  Use live key only after internet-research live verification PASS." >&2
  exit 1
fi

cd "${REPO_ROOT}/backend"
python3 scripts/stripe_seed_research_lookup_meter.py | tee /tmp/research-lookup-stripe-env.txt

STRIPE_RESEARCH_LOOKUP_METERED_PRICE_ID="$(grep '^STRIPE_RESEARCH_LOOKUP_METERED_PRICE_ID=' /tmp/research-lookup-stripe-env.txt | cut -d= -f2-)"
STRIPE_RESEARCH_LOOKUP_METER_EVENT_NAME="$(grep '^STRIPE_RESEARCH_LOOKUP_METER_EVENT_NAME=' /tmp/research-lookup-stripe-env.txt | cut -d= -f2-)"

if [[ "$PUSH_RAILWAY" == "true" || "$FROM_RAILWAY" == "true" ]]; then
  RAILWAY_BIN="${RAILWAY_BIN:-${HOME}/.railway/bin/railway}"
  if "$RAILWAY_BIN" whoami >/dev/null 2>&1; then
    echo ""
    echo "==> Setting Railway vars on ${RAILWAY_SERVICE}..."
    "$RAILWAY_BIN" variables --service "$RAILWAY_SERVICE" \
      set "STRIPE_RESEARCH_LOOKUP_METER_EVENT_NAME=${STRIPE_RESEARCH_LOOKUP_METER_EVENT_NAME}" \
      "STRIPE_RESEARCH_LOOKUP_METERED_PRICE_ID=${STRIPE_RESEARCH_LOOKUP_METERED_PRICE_ID}"
    echo "Railway vars set (staging/test Price ID)."
  fi
fi

TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
python3 - <<PY
import json
from pathlib import Path

path = Path("${REPO_ROOT}/docs/delivery/research-lookups-go-live-status.json")
record = json.loads(path.read_text(encoding="utf-8"))
record["updated_at"] = "${TIMESTAMP}"
record["steps"]["2_stripe_meter_price"] = {
    "status": "PASS",
    "detail": f"stripe_seed_research_lookup_meter.py sk_test @ ${TIMESTAMP} price_id=${STRIPE_RESEARCH_LOOKUP_METERED_PRICE_ID}",
    "mode": "test",
    "price_id": "${STRIPE_RESEARCH_LOOKUP_METERED_PRICE_ID}",
    "event_name": "${STRIPE_RESEARCH_LOOKUP_METER_EVENT_NAME}",
}
if "${PUSH_RAILWAY}" == "true" or "${FROM_RAILWAY}" == "true":
    record["steps"]["3_railway_env_vars"] = {
        "status": "PASS",
        "detail": f"railway variables set @ ${TIMESTAMP} service=${RAILWAY_SERVICE}",
    }
path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(f"Updated {path}")
PY
