#!/usr/bin/env bash
# Set GitHub Actions secret RAILWAY_TOKEN from backend/.env.operator.local
set -euo pipefail
REPO="${1:-cesarbohjr/gravitre-saas-backend}"
ENV_FILE="${2:-backend/.env.operator.local}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE — add RAILWAY_TOKEN=... (Railway project token)" >&2
  exit 1
fi
TOKEN="$(grep -E '^RAILWAY_TOKEN=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '"')"
if [[ -z "$TOKEN" ]]; then
  echo "RAILWAY_TOKEN not found in $ENV_FILE" >&2
  exit 1
fi
echo "Setting RAILWAY_TOKEN on $REPO ..."
printf '%s' "$TOKEN" | gh secret set RAILWAY_TOKEN --repo "$REPO"
echo "Done. Re-run workflow: Milestone 2 Latency A/B"
