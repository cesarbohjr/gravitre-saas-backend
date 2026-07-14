import { headers } from "next/headers"

/**
 * Best-effort visitor country for consent-banner scoping (Vercel geo header).
 * Empty string when unavailable (local/dev) — banner stays hidden unless forced.
 */
export async function getMarketingVisitorCountry(): Promise<string> {
  const headerStore = await headers()
  const country =
    headerStore.get("x-vercel-ip-country") ||
    headerStore.get("cf-ipcountry") ||
    headerStore.get("x-country-code") ||
    ""
  return country.trim().toUpperCase()
}
