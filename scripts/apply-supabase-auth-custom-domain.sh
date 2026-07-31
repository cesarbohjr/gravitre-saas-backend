#!/usr/bin/env bash
# Configure Supabase Auth custom domain (auth.gravitre.app) so OAuth consent
# shows Gravitre branding instead of *.supabase.co.
#
# Prerequisites:
#   - Supabase Pro+ with Custom Domain add-on
#   - DNS: CNAME auth.gravitre.app -> <project-ref>.supabase.co
#   - SUPABASE_ACCESS_TOKEN (https://supabase.com/dashboard/account/tokens)
#
# Usage:
#   SUPABASE_ACCESS_TOKEN=sbp_... bash scripts/apply-supabase-auth-custom-domain.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_REF="${SUPABASE_PROJECT_REF:-smyeexlrqdpymwjmgzqu}"
AUTH_HOST="${SUPABASE_AUTH_HOST:-auth.gravitre.app}"
APP_URL="${NEXT_PUBLIC_APP_URL:-https://gravitre.app}"

if [[ -z "${SUPABASE_ACCESS_TOKEN:-}" ]]; then
  echo "ERROR: SUPABASE_ACCESS_TOKEN is required." >&2
  echo "  Create at https://supabase.com/dashboard/account/tokens" >&2
  exit 1
fi

if ! command -v supabase >/dev/null 2>&1 && command -v npx >/dev/null 2>&1; then
  SUPABASE=(npx --yes supabase)
else
  SUPABASE=(supabase)
fi

echo "==> Link project ${PROJECT_REF}"
(cd "${REPO_ROOT}" && "${SUPABASE[@]}" link --project-ref "${PROJECT_REF}" --yes) || true

echo ""
echo "==> Create custom domain ${AUTH_HOST} (if not exists)"
set +e
"${SUPABASE[@]}" domains create --project-ref "${PROJECT_REF}" --custom-hostname "${AUTH_HOST}" 2>&1
create_exit=$?
set -e
if [[ $create_exit -ne 0 ]]; then
  echo "    (domain may already exist — continuing)"
fi

echo ""
echo "==> Reverify DNS + issue certificate"
"${SUPABASE[@]}" domains reverify --project-ref "${PROJECT_REF}" || true

echo ""
echo "==> Activate custom domain (when DNS + TXT records are ready)"
echo "    Run manually after DNS propagates:"
echo "      supabase domains activate --project-ref ${PROJECT_REF}"
echo ""
echo "==> Google Cloud Console — add Authorized redirect URI:"
echo "      https://${AUTH_HOST}/auth/v1/callback"
echo "      https://${PROJECT_REF}.supabase.co/auth/v1/callback  (keep until cutover verified)"
echo ""
echo "==> Vercel production env (after activate):"
echo "      NEXT_PUBLIC_SUPABASE_AUTH_URL=https://${AUTH_HOST}"
echo "      SUPABASE_PROJECT_URL=https://${PROJECT_REF}.supabase.co"
echo "      NEXT_PUBLIC_APP_URL=${APP_URL}"
echo ""
echo "==> Supabase Auth Site URL (should already be ${APP_URL})"
echo "      npm run auth:sync-urls"
