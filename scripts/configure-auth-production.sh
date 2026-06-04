#!/usr/bin/env bash
# Configure Supabase auth redirect URLs + Vercel production env via CLI/API.
# Requires: SUPABASE_ACCESS_TOKEN, VERCEL_TOKEN
# Optional: SUPABASE_PROJECT_REF (auto-discovered when omitted)
set -euo pipefail

APP_URL="${NEXT_PUBLIC_APP_URL:-https://gravitre.app}"
SUPABASE_API="https://api.supabase.com/v1"
VERCEL_API="https://api.vercel.com"

REDIRECT_URLS=(
  "${APP_URL}/auth/callback"
  "${APP_URL}/**"
  "http://localhost:3000/auth/callback"
  "http://localhost:3000/**"
  "https://localhost:3000/auth/callback"
  "https://localhost:3000/**"
)

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: missing required command: $1" >&2
    exit 1
  fi
}

join_by_comma() {
  local IFS=,
  echo "$*"
}

discover_supabase_project_ref() {
  if [[ -n "${SUPABASE_PROJECT_REF:-}" ]]; then
    echo "$SUPABASE_PROJECT_REF"
    return
  fi

  echo "Discovering Supabase project ref from Management API..." >&2
  local projects
  projects="$(curl -fsS "${SUPABASE_API}/projects" \
    -H "Authorization: Bearer ${SUPABASE_ACCESS_TOKEN}")"

  local ref
  ref="$(echo "$projects" | python3 - <<'PY'
import json, os, sys
data = json.load(sys.stdin)
if not data:
    sys.exit("No Supabase projects returned for this access token.")
name_hint = os.environ.get("SUPABASE_PROJECT_NAME_HINT", "gravitre").lower()
for p in data:
    name = (p.get("name") or "").lower()
    ref = p.get("id") or p.get("ref") or ""
    if name_hint in name or "gravitre" in name or "operator" in name:
        print(ref)
        sys.exit(0)
print(data[0].get("id") or data[0].get("ref") or "")
PY
)"

  if [[ -z "$ref" ]]; then
    echo "ERROR: could not determine SUPABASE_PROJECT_REF. Set it explicitly." >&2
    exit 1
  fi

  echo "$ref"
}

configure_supabase_auth() {
  local project_ref="$1"
  local allow_list
  allow_list="$(join_by_comma "${REDIRECT_URLS[@]}")"

  echo "==> Supabase auth config for project ${project_ref}"
  echo "    site_url=${APP_URL}"

  local payload
  payload="$(python3 - <<PY
import json
print(json.dumps({
    "site_url": "${APP_URL}",
    "uri_allow_list": "${allow_list}",
}))
PY
)"

  curl -fsS -X PATCH "${SUPABASE_API}/projects/${project_ref}/config/auth" \
    -H "Authorization: Bearer ${SUPABASE_ACCESS_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$payload" >/dev/null

  echo "    Supabase redirect URLs updated."

  local google_callback="https://${project_ref}.supabase.co/auth/v1/callback"
  echo ""
  echo "Google OAuth authorized redirect URI (verify in Google Cloud Console):"
  echo "  ${google_callback}"
}

discover_vercel_project() {
  local project="${VERCEL_PROJECT:-gravitre-saas-backend}"
  local team="${VERCEL_ORG_ID:-team_kuQmNfrn5RtMeaWuH88LLuAf}"

  if [[ -n "${VERCEL_PROJECT_ID:-}" ]]; then
    echo "${VERCEL_PROJECT_ID}|${team}"
    return
  fi

  local response
  response="$(curl -fsS "${VERCEL_API}/v9/projects/${project}?teamId=${team}" \
    -H "Authorization: Bearer ${VERCEL_TOKEN}")"

  local project_id
  project_id="$(echo "$response" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
  echo "${project_id}|${team}"
}

upsert_vercel_env() {
  local key="$1"
  local value="$2"
  local project_id="$3"
  local team_id="$4"

  curl -fsS -X POST "${VERCEL_API}/v10/projects/${project_id}/env?teamId=${team_id}" \
    -H "Authorization: Bearer ${VERCEL_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$(python3 - <<PY
import json
print(json.dumps({
    "key": "${key}",
    "value": """${value}""",
    "type": "plain",
    "target": ["production", "preview", "development"],
    "upsert": True,
}))
PY
)" >/dev/null
}

configure_vercel_env() {
  echo "==> Vercel environment variables"

  local project_info project_id team_id
  project_info="$(discover_vercel_project)"
  project_id="${project_info%%|*}"
  team_id="${project_info##*|}"

  if [[ -z "${NEXT_PUBLIC_SUPABASE_URL:-}" || -z "${NEXT_PUBLIC_SUPABASE_ANON_KEY:-}" ]]; then
    echo "WARNING: NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY not set; skipping Supabase public env upsert." >&2
  else
    upsert_vercel_env "NEXT_PUBLIC_SUPABASE_URL" "$NEXT_PUBLIC_SUPABASE_URL" "$project_id" "$team_id"
    upsert_vercel_env "NEXT_PUBLIC_SUPABASE_ANON_KEY" "$NEXT_PUBLIC_SUPABASE_ANON_KEY" "$project_id" "$team_id"
    echo "    Updated NEXT_PUBLIC_SUPABASE_* on Vercel project ${project_id}"
  fi

  upsert_vercel_env "NEXT_PUBLIC_APP_URL" "$APP_URL" "$project_id" "$team_id"
  echo "    Updated NEXT_PUBLIC_APP_URL=${APP_URL}"
}

deploy_vercel_production() {
  if [[ "${SKIP_VERCEL_DEPLOY:-0}" == "1" ]]; then
    echo "==> Skipping Vercel deploy (SKIP_VERCEL_DEPLOY=1)"
    return
  fi

  echo "==> Triggering Vercel production deployment"
  require_cmd npx
  npx --yes vercel deploy --prod --yes --token "$VERCEL_TOKEN" \
    ${VERCEL_ORG_ID:+--scope "$VERCEL_ORG_ID"} \
    --cwd apps/web
}

verify_production() {
  echo "==> Verifying production endpoints"
  curl -fsSI "${APP_URL}/auth/callback?code=invalid-test" | grep -i '^location:' || true
  curl -fsSI "${APP_URL}/operator" | grep -E '^(HTTP/|location:)' || true
  echo "    Production checks complete (307 to /login without session_expired is expected for invalid code)."
}

main() {
  require_cmd curl
  require_cmd python3

  local skip_supabase=0
  if [[ -z "${SUPABASE_ACCESS_TOKEN:-}" ]]; then
    echo "WARNING: SUPABASE_ACCESS_TOKEN not set; skipping Supabase Management API patch." >&2
    echo "  Use: npm run auth:supabase-google  (linked Supabase CLI)" >&2
    echo "  Or create a token: https://supabase.com/dashboard/account/tokens" >&2
    skip_supabase=1
  fi

  if [[ -z "${VERCEL_TOKEN:-}" ]]; then
    echo "ERROR: VERCEL_TOKEN is required." >&2
    echo "Create one at https://vercel.com/account/tokens" >&2
    exit 1
  fi

  if [[ "$skip_supabase" -eq 0 ]]; then
    local project_ref
    project_ref="$(discover_supabase_project_ref)"
    export SUPABASE_PROJECT_REF="$project_ref"
    configure_supabase_auth "$project_ref"
  else
    export SUPABASE_PROJECT_REF="${SUPABASE_PROJECT_REF:-smyeexlrqdpymwjmgzqu}"
  fi
  configure_vercel_env
  deploy_vercel_production
  verify_production

  echo ""
  echo "Done. Supabase project: ${project_ref}"
  echo "Site URL: ${APP_URL}"
}

main "$@"
