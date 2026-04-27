import { getSelectedOrgFromStorage } from "@/lib/org-context"
import { supabaseClient } from "@/lib/supabaseClient"

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

async function withAuthHeader(headers: Headers): Promise<Headers> {
  if (typeof window === "undefined" || headers.has("authorization")) {
    return headers
  }
  try {
    const { data } = await supabaseClient.auth.getSession()
    const token = data.session?.access_token
    if (token) {
      headers.set("authorization", `Bearer ${token}`)
    }
  } catch {
    // Keep request unauthenticated if session cannot be loaded.
  }
  return headers
}

export async function apiFetch(url: string, init?: RequestInit): Promise<Response> {
  const headers = await withAuthHeader(new Headers(init?.headers))
  if (!headers.has("accept")) {
    headers.set("accept", "application/json")
  }
  const response = await fetch(withSelectedOrg(url), {
    ...init,
    headers,
    cache: init?.cache ?? "no-store",
  })
  if (response.status === 401 && typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("gravitre:unauthorized"))
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
