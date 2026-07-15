import { MARKETING_GTG_FPS_HOST, MARKETING_GTG_PATH } from "@/lib/marketing-gtm"

export const runtime = "edge"

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length",
])

type RouteContext = {
  params: Promise<{ path?: string[] }>
}

async function proxyToTagGateway(request: Request, context: RouteContext): Promise<Response> {
  const { path: segments } = await context.params
  const incoming = new URL(request.url)
  // Preserve the first-party measurement path prefix on the FPS origin
  // (Google expects /gtg/healthy, not /healthy).
  const pathSuffix = segments?.length
    ? `${MARKETING_GTG_PATH}/${segments.join("/")}`
    : `${MARKETING_GTG_PATH}/`
  const target = new URL(`https://${MARKETING_GTG_FPS_HOST}${pathSuffix}`)
  target.search = incoming.search

  const headers = new Headers()
  request.headers.forEach((value, key) => {
    if (HOP_BY_HOP.has(key.toLowerCase())) return
    headers.set(key, value)
  })
  // Tag ID is conveyed via the Host subdomain (gtm-….fps.goog). Do not also set
  // X-Gtg-Tag-Id — FPS returns "Tag ID is in both Header and Host subdomain."
  headers.set("Host", MARKETING_GTG_FPS_HOST)
  applyGeoHeaders(request, headers)

  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: "manual",
  }
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = request.body
    // Required for streaming request bodies on some runtimes.
    ;(init as RequestInit & { duplex?: string }).duplex = "half"
  }

  const upstream = await fetch(target, init)
  const responseHeaders = new Headers()
  upstream.headers.forEach((value, key) => {
    if (HOP_BY_HOP.has(key.toLowerCase())) return
    responseHeaders.set(key, value)
  })

  // Measurement beacons must not be cached by intermediaries.
  if (request.method !== "GET" && request.method !== "HEAD") {
    responseHeaders.set("Cache-Control", "no-store")
  }

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  })
}

function applyGeoHeaders(request: Request, headers: Headers): void {
  const country = (request.headers.get("x-vercel-ip-country") || "").trim().toUpperCase()
  const region = (request.headers.get("x-vercel-ip-country-region") || "").trim().toUpperCase()
  const city = (request.headers.get("x-vercel-ip-city") || "").trim()
  const lat = (request.headers.get("x-vercel-ip-latitude") || "").trim()
  const lng = (request.headers.get("x-vercel-ip-longitude") || "").trim()

  if (country) {
    headers.set("X-Forwarded-Country", country)
  }
  if (region) {
    headers.set("X-Forwarded-Region", region)
  }
  if (country && region) {
    headers.set("X-Forwarded-CountryRegion", `${country}-${region}`)
  } else if (country) {
    headers.set("X-Forwarded-CountryRegion", country)
  }

  if (lat && lng) {
    const cityPart = city ? `;city=${city}` : ""
    headers.set("X-Forwarded-Geolocation", `latlong=${lat},${lng}${cityPart}`)
  }
}

export const GET = proxyToTagGateway
export const HEAD = proxyToTagGateway
export const POST = proxyToTagGateway
export const PUT = proxyToTagGateway
export const PATCH = proxyToTagGateway
export const DELETE = proxyToTagGateway
export const OPTIONS = proxyToTagGateway
