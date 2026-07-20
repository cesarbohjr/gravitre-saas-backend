#!/usr/bin/env bash
# Apply Research Lookups billing migration + verify + Stripe meter seed + Railway env hints.
#
# Prerequisites (one of):
#   - SUPABASE_ACCESS_TOKEN (+ optional SUPABASE_DB_PASSWORD) for `supabase db push`
#   - STRIPE_SECRET_KEY for meter/price creation
#   - Railway CLI logged in (`railway login`) for variable push
#
# Does NOT flip INTERNET_RESEARCH_ENABLED or NEXT_PUBLIC_INTERNET_RESEARCH_ENABLED.
# Does NOT attach metered price to production subscriptions.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_REF="${SUPABASE_PROJECT_REF:-smyeexlrqdpymwjmgzqu}"
RAILWAY_SERVICE="${RAILWAY_SERVICE:-gravitre-saas-backend}"
MIGRATION="20260719120000_billing_plans_research_lookups.sql"
STATUS_JSON="${REPO_ROOT}/docs/delivery/research-lookups-go-live-status.json"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

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

step_migration="NOT_RUN"
step_stripe="NOT_RUN"
step_railway="NOT_RUN"
migration_detail=""
stripe_detail=""
railway_detail=""

echo "==> Research Lookups billing go-live prep (${TIMESTAMP})"
echo "    Project ref: ${PROJECT_REF}"
echo "    Target migration: supabase/migrations/${MIGRATION}"
echo ""

if command -v supabase >/dev/null 2>&1 || command -v npx >/dev/null 2>&1; then
  SUPABASE_CMD=(supabase)
  if ! command -v supabase >/dev/null 2>&1; then
    SUPABASE_CMD=(npx --yes supabase)
  fi

  if [[ -n "${SUPABASE_ACCESS_TOKEN:-}" ]]; then
    echo "==> Linking Supabase project ${PROJECT_REF}..."
    (cd "${REPO_ROOT}" && "${SUPABASE_CMD[@]}" link --project-ref "${PROJECT_REF}" --yes) || true

    echo "==> Applying pending migrations (supabase db push)..."
    if (cd "${REPO_ROOT}" && "${SUPABASE_CMD[@]}" db push); then
      step_migration="PASS"
      migration_detail="supabase db push @ ${TIMESTAMP}"

      echo "==> Verifying billing_plans + usage_records.stripe_reported_at..."
      if (cd "${REPO_ROOT}" && "${SUPABASE_CMD[@]}" db query --linked -f supabase/scripts/verify_research_lookups_billing.sql); then
        migration_detail="${migration_detail}; verify SQL ok"
      else
        step_migration="PARTIAL"
        migration_detail="${migration_detail}; verify SQL failed"
      fi
    else
      step_migration="FAIL"
      migration_detail="supabase db push failed @ ${TIMESTAMP}"
    fi
  else
    migration_detail="missing SUPABASE_ACCESS_TOKEN — run: supabase login or set token in backend/.env.operator.local"
    echo "SKIP migration: ${migration_detail}"
  fi
else
  migration_detail="supabase CLI not installed"
  echo "SKIP migration: ${migration_detail}"
fi

echo ""
if [[ -n "${STRIPE_SECRET_KEY:-}" ]]; then
  echo "==> Creating Stripe meter + \$0.35 price via API..."
  if python3 "${REPO_ROOT}/backend/scripts/stripe_seed_research_lookup_meter.py" | tee /tmp/research-lookup-stripe-env.txt; then
    step_stripe="PASS"
    stripe_detail="stripe_seed_research_lookup_meter.py @ ${TIMESTAMP}"
    STRIPE_RESEARCH_LOOKUP_METERED_PRICE_ID="$(grep '^STRIPE_RESEARCH_LOOKUP_METERED_PRICE_ID=' /tmp/research-lookup-stripe-env.txt | cut -d= -f2- || true)"
    STRIPE_RESEARCH_LOOKUP_METER_EVENT_NAME="$(grep '^STRIPE_RESEARCH_LOOKUP_METER_EVENT_NAME=' /tmp/research-lookup-stripe-env.txt | cut -d= -f2- || true)"
  else
    step_stripe="FAIL"
    stripe_detail="stripe seed script failed @ ${TIMESTAMP}"
  fi
else
  stripe_detail="missing STRIPE_SECRET_KEY — Dashboard steps in docs/delivery/stripe-research-lookups-meter-spec.md"
  echo "SKIP Stripe seed: ${stripe_detail}"
fi

echo ""
RAILWAY_BIN="${RAILWAY_BIN:-}"
if [[ -z "$RAILWAY_BIN" && -x "${HOME}/.railway/bin/railway" ]]; then
  RAILWAY_BIN="${HOME}/.railway/bin/railway"
elif command -v railway >/dev/null 2>&1; then
  RAILWAY_BIN="railway"
fi

if [[ -n "$RAILWAY_BIN" && -n "${STRIPE_RESEARCH_LOOKUP_METERED_PRICE_ID:-}" ]]; then
  echo "==> Pushing Stripe env vars to Railway service ${RAILWAY_SERVICE}..."
  if "$RAILWAY_BIN" whoami >/dev/null 2>&1; then
    "$RAILWAY_BIN" variables --service "${RAILWAY_SERVICE}" \
      set "STRIPE_RESEARCH_LOOKUP_METER_EVENT_NAME=${STRIPE_RESEARCH_LOOKUP_METER_EVENT_NAME:-research_lookups_used}" \
      "STRIPE_RESEARCH_LOOKUP_METERED_PRICE_ID=${STRIPE_RESEARCH_LOOKUP_METERED_PRICE_ID}"
    step_railway="PASS"
    railway_detail="railway variables set @ ${TIMESTAMP} service=${RAILWAY_SERVICE}"
  else
    railway_detail="railway not logged in — run: railway login"
    echo "SKIP Railway: ${railway_detail}"
    echo "Manual:"
    echo "  STRIPE_RESEARCH_LOOKUP_METER_EVENT_NAME=${STRIPE_RESEARCH_LOOKUP_METER_EVENT_NAME:-research_lookups_used}"
    echo "  STRIPE_RESEARCH_LOOKUP_METERED_PRICE_ID=${STRIPE_RESEARCH_LOOKUP_METERED_PRICE_ID}"
  fi
elif [[ -n "$RAILWAY_BIN" ]]; then
  railway_detail="no Price ID from Stripe step — set Railway vars after Dashboard/API seed"
  echo "SKIP Railway: ${railway_detail}"
else
  railway_detail="railway CLI not found"
  echo "SKIP Railway: ${railway_detail}"
fi

mkdir -p "$(dirname "${STATUS_JSON}")"
python3 - <<PY
import json
from pathlib import Path

path = Path("${STATUS_JSON}")
record = {
    "record": "research_lookups_go_live_status",
    "updated_at": "${TIMESTAMP}",
    "sequencing": "flag_gated — do not flip INTERNET_RESEARCH_ENABLED or NEXT_PUBLIC_INTERNET_RESEARCH_ENABLED until live verification PASS",
    "do_not_before_live_pass": [
        "attach STRIPE_RESEARCH_LOOKUP_METERED_PRICE_ID to production subscriptions",
        "INTERNET_RESEARCH_ENABLED=true on Railway",
        "NEXT_PUBLIC_INTERNET_RESEARCH_ENABLED=true on Vercel",
    ],
    "go_live_together": [
        "INTERNET_RESEARCH_ENABLED=true (Railway)",
        "NEXT_PUBLIC_INTERNET_RESEARCH_ENABLED=true (Vercel)",
    ],
    "deferred_follow_up": "outputs/mesons auto-billing parity (pre-existing gap — docs/delivery/outputs-meson-billing-mechanism-audit.json)",
    "steps": {
        "1_migration_prod_staging": {"status": "${step_migration}", "detail": "${migration_detail}"},
        "2_stripe_meter_price": {"status": "${step_stripe}", "detail": "${stripe_detail}"},
        "3_railway_env_vars": {"status": "${step_railway}", "detail": "${railway_detail}"},
    },
    "migration_files": [
        "supabase/migrations/20260718120000_internet_research_metering.sql",
        "supabase/migrations/20260718130000_internet_research_circuit_breaker.sql",
        "supabase/migrations/${MIGRATION}",
    ],
}
path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(f"Wrote status: {path}")
PY

echo ""
echo "==> Summary"
echo "    Migration: ${step_migration}"
echo "    Stripe:    ${step_stripe}"
echo "    Railway:   ${step_railway}"
echo "    Status:    ${STATUS_JSON}"

if [[ "${step_migration}" == "FAIL" || "${step_stripe}" == "FAIL" ]]; then
  exit 1
fi
