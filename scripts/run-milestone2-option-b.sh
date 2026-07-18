#!/usr/bin/env bash
# Milestone 2 Option B — local pre/post RM latency A/B (requires backend/.env.operator.local)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
AB_JSON="docs/delivery/milestone2-latency-ab-latest.json"
PRE_JSON="docs/delivery/milestone2-latency-pre-rm-probe.json"
AUDIT_JSON="docs/delivery/milestone2-performance-audit-latest.json"

if [[ ! -f backend/.env.operator.local && ! -f .env.operator.local ]]; then
  echo "Missing backend/.env.operator.local — need at least:" >&2
  echo "  RAILWAY_TOKEN, SUPABASE_URL, SUPABASE_JWT_SECRET, SUPABASE_SERVICE_ROLE_KEY" >&2
  exit 2
fi

echo "=== Milestone 2 Option B: full latency A/B ==="
python3 scripts/smoke-milestone2-latency-ab.py --full-ab --json "$AB_JSON"
python3 scripts/smoke-milestone2-performance-audit.py --latency-baseline "$PRE_JSON" --json "$AUDIT_JSON"
echo "=== Done — see $AB_JSON and $AUDIT_JSON ==="
