export async function fetcher<T>(url: string): Promise<T> {
  const response = await fetch(url, {
    headers: {
      accept: "application/json",
    },
    cache: "no-store",
  })

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
