import { getSelectedOrgFromStorage } from "@/lib/org-context"
import { getAccessToken } from "@/lib/auth-context"

function withSelectedOrg(url: string): string {
  if (typeof window === "undefined" || !url.startsWith("/api/")) return url
  const selected = getSelectedOrgFromStorage()
  if (!selected?.id) return url
  const requestUrl = new URL(url, window.location.origin)
  if (!requestUrl.searchParams.get("org_id")) {
    requestUrl.searchParams.set("org_id", selected.id)
  }
  return `${requestUrl.pathname}${requestUrl.search}`
}

export async function apiFetch(url: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers)
  if (!headers.has("accept")) {
    headers.set("accept", "application/json")
  }
  
  // Add auth token if available
  if (typeof window !== "undefined") {
    const token = await getAccessToken()
    if (token && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${token}`)
    }
  }
  
  const response = await fetch(withSelectedOrg(url), {
    ...init,
    headers,
    cache: init?.cache ?? "no-store",
  })
  
  // Handle 401 by redirecting to login
  if (response.status === 401 && typeof window !== "undefined") {
    window.location.assign("/login?session_expired=true")
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
