/**
 * Demo / local-only fabricated stores (demo-runtime-store) must never back
 * real customer traffic under misconfiguration.
 *
 * Standing rule: never show fabricated data as if real.
 *
 * Audit (2026-07-19):
 * - `ensureDemoDataForOrg` (demo-bootstrap) already no-ops unless org_id is one of
 *   the two hardcoded demo UUIDs (00000000-…0001 / 11111111-…1111). Real customer
 *   orgs cannot receive that seed under any org_id misconfiguration.
 * - FASTAPI_BASE_URL-unset fallbacks previously returned in-memory demo approvals /
 *   sessions / training to *any* caller. That path is now fail-closed unless
 *   ALLOW_DEMO_RUNTIME_FALLBACK=1 and the deployment is not Vercel production.
 */

export function isFastApiConfigured(): boolean {
  return Boolean(process.env.FASTAPI_BASE_URL?.trim())
}

/** True only for explicit local/demo opt-in — never Vercel production. */
export function isDemoRuntimeFallbackAllowed(): boolean {
  if (process.env.VERCEL_ENV === "production") return false
  return process.env.ALLOW_DEMO_RUNTIME_FALLBACK === "1"
}

export function shouldUseDemoRuntimeFallback(): boolean {
  return !isFastApiConfigured() && isDemoRuntimeFallbackAllowed()
}
