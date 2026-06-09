import { getSelectedOrgFromStorage, DEFAULT_DEMO_ORG_ID, SECONDARY_DEMO_ORG_ID } from "@/lib/org-context"
import { getAccessToken } from "@/lib/auth-context"
import { clearAuthTransition } from "@/lib/auth-transition"
import { supabaseClient } from "@/lib/supabaseClient"

function withSelectedOrg(url: string): string {
  if (typeof window === "undefined" || !url.startsWith("/api/")) return url
  const selected = getSelectedOrgFromStorage()
  // Skip demo org ids in query params — they cause org context mismatches server-side.
  if (
    !selected?.id ||
    selected.id === DEFAULT_DEMO_ORG_ID ||
    selected.id === SECONDARY_DEMO_ORG_ID
  ) {
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
    if (
      selectedOrg?.id &&
      selectedOrg.id !== DEFAULT_DEMO_ORG_ID &&
      selectedOrg.id !== SECONDARY_DEMO_ORG_ID &&
      !headers.has("x-org-id")
    ) {
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

export async function fetcher<T>(url: string): Promise<T> {
  const response = await apiFetch(url)

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`
    try {
      const payload = await response.json()
      if (payload?.detail) {
        detail = String(payload.detail)
      } else if (payload?.error) {
        detail = String(payload.error)
      }
    } catch {
      // Keep default detail when body is not JSON.
    }
    throw new Error(detail)
  }

  return response.json() as Promise<T>
}
