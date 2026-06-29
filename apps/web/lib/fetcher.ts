import { getSelectedOrgFromStorage } from "@/lib/org-context"
import { getAccessToken } from "@/lib/auth-context"
import { clearAuthTransition } from "@/lib/auth-transition"
import { emitPlanRequired, type PlanRequiredDetail } from "@/lib/billing-plan-required"
import { supabaseClient } from "@/lib/supabaseClient"

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
    const { data: { user } } = await supabaseClient.auth.getUser()
    return Boolean(user)
  } catch {
    return false
  }
}

export async function apiFetch(url: string, init?: RequestInit): Promise<Response> {
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
  }

  const response = await fetch(withSelectedOrg(url), {
    ...init,
    headers,
    cache: init?.cache ?? "no-store",
  })

  if (response.ok && typeof window !== "undefined") {
    window.sessionStorage.removeItem("gravitre_auth_login_redirect")
  }

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

  if (response.status === 401 && typeof window !== "undefined") {
    const currentPath = window.location.pathname
    const deferredAuthPages = [
      "/get-started",
      "/login",
      "/forgot-password",
      "/auth",
    ]
    const shouldSkipRedirect = deferredAuthPages.some((page) =>
      currentPath.startsWith(page)
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
  if (!payload || typeof payload !== "object") return null
  const data = payload as Record<string, unknown>

  const detail = data.detail
  if (typeof detail === "string" && detail.trim()) return detail
  if (detail && typeof detail === "object") {
    const detailObj = detail as Record<string, unknown>
    if (typeof detailObj.message === "string" && detailObj.message.trim()) {
      return detailObj.message
    }
  }
  if (Array.isArray(detail)) {
    const first = detail[0]
    if (first && typeof first === "object") {
      const msg = (first as Record<string, unknown>).msg
      if (typeof msg === "string" && msg.trim()) return msg
    }
  }

  const error = data.error
  if (typeof error === "string" && error.trim()) return error
  if (error && typeof error === "object") {
    const errorObj = error as Record<string, unknown>
    if (typeof errorObj.message === "string" && errorObj.message.trim()) return errorObj.message
    if (typeof errorObj.code === "string" && errorObj.code.trim()) return errorObj.code
  }
  return null
}

export async function fetcher<T>(url: string): Promise<T> {
  const response = await apiFetch(url)

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`
    try {
      const payload = await response.json()
      detail = formatErrorPayload(payload) ?? detail
    } catch {
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
