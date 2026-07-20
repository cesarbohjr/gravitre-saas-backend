/**
 * Client chokepoint companion to backend conversation_write_guard.
 * Smoke/Playwright runs that flag themselves must not create threads in the
 * operator workspace (cbbf993b-…).
 */

export const FORBIDDEN_OPERATOR_ORG_ID = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
export const ISOLATED_CONVERSATION_TEST_ORG_ID =
  process.env.NEXT_PUBLIC_ISOLATED_CONVERSATION_TEST_ORG_ID?.trim() ||
  "f07e57c0-1501-4000-8000-c04e57a00001"

declare global {
  interface Window {
    __GRAVITREE_SMOKE_RUN__?: boolean | string
  }
}

export function isBrowserSmokeRun(): boolean {
  if (typeof window !== "undefined") {
    const flag = window.__GRAVITREE_SMOKE_RUN__
    if (flag === true || flag === "1" || flag === "true") return true
  }
  const envFlag = process.env.NEXT_PUBLIC_GRAVITREE_SMOKE_RUN?.trim().toLowerCase()
  return envFlag === "1" || envFlag === "true" || envFlag === "yes"
}

export function assertConversationCreateOrgAllowed(orgId: string | null | undefined): void {
  if (!isBrowserSmokeRun()) return
  const oid = (orgId || "").trim().toLowerCase()
  const allowed = ISOLATED_CONVERSATION_TEST_ORG_ID.toLowerCase()
  if (oid && oid === allowed) return
  throw new Error(
    `REFUSING conversation create: smoke/test/CI context cannot write conversations into org ${
      orgId || "<missing>"
    }. Target the isolated test org only (${ISOLATED_CONVERSATION_TEST_ORG_ID}). ` +
      `Operator workspace ${FORBIDDEN_OPERATOR_ORG_ID} is never allowed.`,
  )
}

export function isConversationSmokeGuardError(error: unknown): boolean {
  const msg =
    error instanceof Error
      ? error.message
      : typeof error === "string"
        ? error
        : JSON.stringify(error ?? "")
  return msg.includes("REFUSING conversation create") || msg.includes("isolated test org")
}
