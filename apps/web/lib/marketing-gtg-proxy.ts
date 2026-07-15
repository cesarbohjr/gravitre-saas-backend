import { MARKETING_GTG_FPS_HOST, MARKETING_GTG_PATH } from "@/lib/marketing-gtm"

/** Build the FPS upstream URL, preserving the first-party path + query string. */
export function buildTagGatewayUpstreamUrl(
  requestUrl: string | URL,
  pathSegments?: string[] | null
): URL {
  const incoming = typeof requestUrl === "string" ? new URL(requestUrl) : requestUrl
  const pathSuffix = pathSegments?.length
    ? `${MARKETING_GTG_PATH}/${pathSegments.join("/")}`
    : `${MARKETING_GTG_PATH}/`
  const target = new URL(`https://${MARKETING_GTG_FPS_HOST}${pathSuffix}`)
  // Prefer searchParams copy (NextRequest.nextUrl) so query survives edge/middleware.
  incoming.searchParams.forEach((value, key) => {
    target.searchParams.append(key, value)
  })
  return target
}

/** Map Vercel geo request headers onto the X-Forwarded-* headers FPS expects. */
export function applyTagGatewayGeoHeaders(requestHeaders: Headers, outbound: Headers): void {
  const country = (requestHeaders.get("x-vercel-ip-country") || "").trim().toUpperCase()
  const region = (requestHeaders.get("x-vercel-ip-country-region") || "").trim().toUpperCase()
  const city = (requestHeaders.get("x-vercel-ip-city") || "").trim()
  const lat = (requestHeaders.get("x-vercel-ip-latitude") || "").trim()
  const lng = (requestHeaders.get("x-vercel-ip-longitude") || "").trim()

  if (country) {
    outbound.set("X-Forwarded-Country", country)
  }
  if (region) {
    outbound.set("X-Forwarded-Region", region)
  }
  if (country && region) {
    outbound.set("X-Forwarded-CountryRegion", `${country}-${region}`)
  } else if (country) {
    outbound.set("X-Forwarded-CountryRegion", country)
  }

  if (lat && lng) {
    const cityPart = city ? `;city=${city}` : ""
    outbound.set("X-Forwarded-Geolocation", `latlong=${lat},${lng}${cityPart}`)
  }
}
