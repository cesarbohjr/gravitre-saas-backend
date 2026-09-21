import { extractApiErrorMessage } from "@/lib/api-error-message"
import { getSelectedOrgFromStorage } from "@/lib/org-context"
import { getEnvironmentHeader } from "@/lib/environment-context"
import { getDepartmentHeader } from "@/lib/department-context"
import { getAccessToken } from "@/lib/auth-context"
import { clearAuthTransition } from "@/lib/auth-transition"
import { emitPlanRequired, type PlanRequiredDetail } from "@/lib/billing-plan-required"
import { supabaseClient } from "@/lib/supabaseClient"

/** Default ceiling for browser API calls — prevents infinite spinners on hung backends. */
export const DEFAULT_API_TIMEOUT_MS = 60_000

const ORG_MEMBERSHIP_DENIED_RE = /not a member of the requested organization/i

type ApiFetchInit = RequestInit & {
  timeoutMs?: number
  /** Internal: already attempted stale-org recovery for this call. */
  __orgMembershipRecovered?: boolean
}

function withSelectedOrg(url: string): string {
  if (typeof window === "undefined" || !url.startsWith("/api/")) return url
  const selected = getSelectedOrgFromStorage()
  if (!selected?.id) {
    return url
  }
  const requestUrl = new URL(url, window.location.origin)
  if (!requestUrl.searchParams.get("org_id")) {
    requestUrl.searchParams.set("org_id", selected.id)
  }
  return `${requestUrl.pathname}${requestUrl.search}`
}

async function hasLiveSupabaseSession(): Promise<boolean> {
  try {
    // Bound the call: supabase-js getUser() can hang during a concurrent
    // refresh, which would otherwise stall the 401 handling path forever.
    const result = await Promise.race([
      supabaseClient.auth.getUser(),
      new Promise<null>((resolve) => setTimeout(() => resolve(null), 5000)),
    ])
    return Boolean(result?.data?.user)
  } catch {
    return false
  }
}

async function maybeRecoverStaleOrgAndRetry(
  url: string,
  init: ApiFetchInit | undefined,
  response: Response,
): Promise<Response | null> {
  if (typeof window === "undefined") return null
  if (response.status !== 403) return null
  if (init?.__orgMembershipRecovered) return null

  let detail = ""
  try {
    const payload = await response.clone().json()
    detail = extractApiErrorMessage(payload) ?? ""
  } catch {
    return null
  }
  if (!ORG_MEMBERSHIP_DENIED_RE.test(detail)) return null

  const { recoverSelectedOrgAfterMembershipDenied } = await import("@/lib/org-context")
  const nextOrgId = await recoverSelectedOrgAfterMembershipDenied()
  if (!nextOrgId) return null

  const retryHeaders = new Headers(init?.headers)
  retryHeaders.delete("x-org-id")
  // Drop stale org_id query so withSelectedOrg injects the recovered id.
  let retryUrl = url
  try {
    if (url.startsWith("/api/")) {
      const parsed = new URL(url, window.location.origin)
      parsed.searchParams.delete("org_id")
      retryUrl = `${parsed.pathname}${parsed.search}`
    }
  } catch {
    retryUrl = url
  }

  return apiFetch(retryUrl, {
    ...init,
    headers: retryHeaders,
    __orgMembershipRecovered: true,
  })
}

export async function apiFetch(
  url: string,
  init?: ApiFetchInit,
): Promise<Response> {
  const headers = new Headers(init?.headers)
  if (!headers.has("accept")) {
    headers.set("accept", "application/json")
  }

  let token: string | null = null
  if (typeof window !== "undefined") {
    token = await getAccessToken()
    if (token && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${token}`)
    }
    const selectedOrg = getSelectedOrgFromStorage()
    if (selectedOrg?.id && !headers.has("x-org-id")) {
      headers.set("x-org-id", selectedOrg.id)
    }
    if (!headers.has("x-environment")) {
      headers.set("x-environment", getEnvironmentHeader())
    }
    const department = getDepartmentHeader()
    if (department && !headers.has("x-department")) {
      headers.set("x-department", department)
    }
  }

  const timeoutMs = init?.timeoutMs ?? DEFAULT_API_TIMEOUT_MS
  const { timeoutMs: _timeoutMs, __orgMembershipRecovered: _recovered, ...fetchInit } = init ?? {}
  const timeoutController = new AbortController()
  const timeoutId = setTimeout(() => {
    timeoutController.abort(new DOMException("Request timed out", "TimeoutError"))
  }, timeoutMs)

  let response: Response
  try {
    response = await fetch(withSelectedOrg(url), {
      ...fetchInit,
      headers,
      cache: fetchInit.cache ?? "no-store",
      signal: fetchInit.signal ?? timeoutController.signal,
    })
  } catch (error) {
    if (
      error instanceof DOMException &&
      (error.name === "TimeoutError" || error.name === "AbortError")
    ) {
      throw new RequestTimeoutError(timeoutMs)
    }
    throw error
  } finally {
    clearTimeout(timeoutId)
  }

  if (response.ok && typeof window !== "undefined") {
    window.sessionStorage.removeItem("gravitre_auth_login_redirect")
  }

  const recovered = await maybeRecoverStaleOrgAndRetry(url, init, response)
  if (recovered) return recovered

  if (response.status === 402 && typeof window !== "undefined") {
    try {
      const payload = (await response.clone().json()) as PlanRequiredDetail
      if (payload?.error === "plan_required") {
        emitPlanRequired(payload)
      }
    } catch {
      // ignore parse errors
    }
  }

  if (response.status === 429) {
    const retryAfterHeader = response.headers.get("Retry-After")
    const retryAfter = retryAfterHeader ? parseInt(retryAfterHeader, 10) : 60
    throw new RateLimitError(Number.isFinite(retryAfter) ? retryAfter : 60)
  }

  if (response.status === 401 && typeof window !== "undefined") {
    const currentPath = window.location.pathname
    const oauthReturn =
      typeof window !== "undefined"
        ? new URLSearchParams(window.location.search).get("oauth")
        : null
    const deferredAuthPages = [
      "/get-started",
      "/login",
      "/forgot-password",
      "/auth",
    ]
    const shouldSkipRedirect = deferredAuthPages.some((page) =>
      currentPath.startsWith(page)
    ) || (
      currentPath.startsWith("/connectors") &&
      (oauthReturn === "success" || oauthReturn === "error")
    )

    if (!shouldSkipRedirect) {
      const alreadyRedirecting =
        window.sessionStorage.getItem("gravitre_auth_login_redirect") === "1"

      // Supabase session may still be valid while the API JWT is rejected (config mismatch).
      if (await hasLiveSupabaseSession()) {
        console.warn(
          "[apiFetch] Backend returned 401 but Supabase session is valid — not signing out.",
        )
        throw new Error("API authentication failed")
      }

      if (!alreadyRedirecting) {
        window.sessionStorage.setItem("gravitre_auth_login_redirect", "1")
        clearAuthTransition()
        const loginUrl = new URL("/login", window.location.origin)
        loginUrl.searchParams.set("error", "session_expired")
        loginUrl.searchParams.set("redirect", currentPath)
        window.location.assign(loginUrl.toString())
      }
    }
    throw new Error("Session expired")
  }

  return response
}

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

export class PlanRequiredApiError extends ApiError {
  planDetail: PlanRequiredDetail

  constructor(planDetail: PlanRequiredDetail) {
    super(
      planDetail.message?.trim() ||
        "Your trial has ended. Upgrade to continue using Gravitre.",
      402,
    )
    this.name = "PlanRequiredApiError"
    this.planDetail = planDetail
  }
}

export class RateLimitError extends ApiError {
  retryAfterSeconds: number

  constructor(retryAfterSeconds: number) {
    super(
      `Too many requests — try again in ${retryAfterSeconds} seconds.`,
      429,
    )
    this.name = "RateLimitError"
    this.retryAfterSeconds = retryAfterSeconds
  }
}

export class RequestTimeoutError extends ApiError {
  timeoutMs: number

  constructor(timeoutMs: number) {
    const seconds = Math.round(timeoutMs / 1000)
    super(
      `Request timed out after ${seconds} seconds. Check your connection and try again.`,
      408,
    )
    this.name = "RequestTimeoutError"
    this.timeoutMs = timeoutMs
  }
}

export function formatUnknownError(error: unknown, fallback = "Something went wrong"): string {
  if (error instanceof Error && error.message.trim()) return error.message
  if (typeof error === "string" && error.trim()) return error
  if (error && typeof error === "object") {
    const record = error as Record<string, unknown>
    if (typeof record.message === "string" && record.message.trim()) return record.message
    if (typeof record.detail === "string" && record.detail.trim()) return record.detail
    if (typeof record.error === "string" && record.error.trim()) return record.error
  }
  return fallback
}

function formatErrorPayload(payload: unknown): string | null {
  return extractApiErrorMessage(payload)
}

export async function fetcher<T>(url: string): Promise<T> {
  const response = await apiFetch(url)

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`
    try {
      const payload = await response.json()
      detail = formatErrorPayload(payload) ?? detail
      if (
        response.status === 402 &&
        payload &&
        typeof payload === "object" &&
        (payload as PlanRequiredDetail).error === "plan_required"
      ) {
        const planDetail = payload as PlanRequiredDetail
        emitPlanRequired(planDetail)
        throw new PlanRequiredApiError(planDetail)
      }
    } catch (parseError) {
      if (parseError instanceof PlanRequiredApiError) {
        throw parseError
      }
      if (parseError instanceof RateLimitError || parseError instanceof RequestTimeoutError) {
        throw parseError
      }
      // Keep default detail when body is not JSON.
    }
    throw new ApiError(detail, response.status)
  }

  const text = await response.text()
  if (!text.trim()) {
    return {} as T
  }
  try {
    return JSON.parse(text) as T
  } catch {
    throw new ApiError("Invalid JSON response from server", response.status)
  }
}

declare global {
  interface Window {
    __gravitreApiFetch?: typeof apiFetch
  }
}

if (typeof window !== "undefined" && process.env.NEXT_PUBLIC_PLAYWRIGHT_E2E === "1") {
  window.__gravitreApiFetch = apiFetch
}
