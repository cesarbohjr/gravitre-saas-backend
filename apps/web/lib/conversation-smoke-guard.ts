/**
 * Client chokepoint companion to backend conversation_write_guard.
 *
 * Default-deny: known smoke/service-account identities cannot create threads
 * outside the isolated test org — even if the caller forgot a smoke flag.
 */

export const FORBIDDEN_OPERATOR_ORG_ID = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
export const ISOLATED_CONVERSATION_TEST_ORG_ID =
  process.env.NEXT_PUBLIC_ISOLATED_CONVERSATION_TEST_ORG_ID?.trim() ||
  "f07e57c0-1501-4000-8000-c04e57a00001"
export const ISOLATED_CONVERSATION_TEST_USER_ID =
  process.env.NEXT_PUBLIC_ISOLATED_CONVERSATION_TEST_USER_ID?.trim() ||
  "a9f1240f-910a-42ca-aebf-38caeac288c3"
export const ISOLATED_CONVERSATION_TEST_EMAIL = "conversation-smoke-sa@gravitre.app"

declare global {
  interface Window {
    __GRAVITRE_SMOKE_RUN__?: boolean | string
    __GRAVITREE_SMOKE_RUN__?: boolean | string
  }
}

const SMOKE_EMAIL_RE =
  /(^conversation-smoke-sa@)|(^ci\+)|(^smoke[-+.]|[-+. ]smoke@)|(@.*\.smoke\.gravitre\.app$)/i

function _truthyFlag(flag: unknown): boolean {
  return flag === true || flag === "1" || flag === "true"
}

export function isBrowserSmokeRun(): boolean {
  if (typeof window !== "undefined") {
    if (_truthyFlag(window.__GRAVITRE_SMOKE_RUN__) || _truthyFlag(window.__GRAVITREE_SMOKE_RUN__)) {
      return true
    }
  }
  const envFlag = (
    process.env.NEXT_PUBLIC_GRAVITRE_SMOKE_RUN ||
    process.env.NEXT_PUBLIC_GRAVITREE_SMOKE_RUN ||
    ""
  )
    .trim()
    .toLowerCase()
  return envFlag === "1" || envFlag === "true" || envFlag === "yes"
}

export function isRestrictedTestCredential(
  userId?: string | null,
  email?: string | null,
): boolean {
  const uid = (userId || "").trim().toLowerCase()
  const mail = (email || "").trim().toLowerCase()
  if (uid && uid === ISOLATED_CONVERSATION_TEST_USER_ID.toLowerCase()) return true
  if (mail && mail === ISOLATED_CONVERSATION_TEST_EMAIL.toLowerCase()) return true
  if (mail && SMOKE_EMAIL_RE.test(mail)) return true
  return false
}

export function assertConversationCreateOrgAllowed(
  orgId: string | null | undefined,
  userId?: string | null,
  email?: string | null,
): void {
  const restricted = isBrowserSmokeRun() || isRestrictedTestCredential(userId, email)
  if (!restricted) return
  const oid = (orgId || "").trim().toLowerCase()
  const allowed = ISOLATED_CONVERSATION_TEST_ORG_ID.toLowerCase()
  if (oid && oid === allowed) return
  throw new Error(
    `REFUSING conversation create: test/service credential cannot write conversations into org ${
      orgId || "<missing>"
    }. Allow-listed org only (${ISOLATED_CONVERSATION_TEST_ORG_ID}). ` +
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
  return (
    msg.includes("REFUSING conversation create") ||
    msg.includes("isolated test org") ||
    msg.includes("Allow-listed org only")
  )
}
