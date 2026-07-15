import type { NextRequest } from "next/server"

import { MARKETING_GTG_FPS_HOST, MARKETING_GTG_PATH } from "@/lib/marketing-gtm"

/** Resolve the inbound query string from several Edge-safe sources. */
export function resolveTagGatewaySearch(request: NextRequest): string {
  if (request.nextUrl.search) return request.nextUrl.search
  try {
    const fromUrl = new URL(request.url).search
    if (fromUrl) return fromUrl
  } catch {
    // ignore malformed request.url
  }
  const invoke = (request.headers.get("x-invoke-query") || "").trim()
  if (invoke) return invoke.startsWith("?") ? invoke : `?${invoke}`
  return ""
}

/** Build the FPS upstream URL, preserving the first-party path + query string. */
export function buildTagGatewayUpstreamUrl(
  search: string,
  pathSegments?: string[] | null
): URL {
  const pathSuffix = pathSegments?.length
    ? `${MARKETING_GTG_PATH}/${pathSegments.join("/")}`
    : `${MARKETING_GTG_PATH}/`
  const target = new URL(`https://${MARKETING_GTG_FPS_HOST}${pathSuffix}`)
  if (search) {
    target.search = search.startsWith("?") ? search.slice(1) : search
  }
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
  // Avoid compressed upstream bodies that some edge fetch stacks mishandle.
  "accept-encoding",
  // Do not forward browser/session cookies or client-spoofable forwarded headers to FPS.
  "cookie",
  "authorization",
  "x-forwarded-host",
  "x-forwarded-proto",
  "x-forwarded-for",
  "x-forwarded-country",
  "x-forwarded-region",
  "x-forwarded-countryregion",
  "x-forwarded-geolocation",
  "x-real-ip",
])

/** Shared Tag Gateway reverse-proxy used by /gtg and /gtg/* route handlers. */
export async function proxyTagGatewayRequest(
  request: NextRequest,
  pathSegments?: string[] | null
): Promise<Response> {
  const search = resolveTagGatewaySearch(request)
  const target = buildTagGatewayUpstreamUrl(search, pathSegments)

  const headers = new Headers()
  request.headers.forEach((value, key) => {
    if (HOP_BY_HOP.has(key.toLowerCase())) return
    headers.set(key, value)
  })
  // Tag ID is conveyed via the Host subdomain (gtm-….fps.goog). Do not also set
  // X-Gtg-Tag-Id — FPS returns "Tag ID is in both Header and Host subdomain."
  headers.set("Host", MARKETING_GTG_FPS_HOST)
  applyTagGatewayGeoHeaders(request.headers, headers)

  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: "manual",
    cache: "no-store",
  }
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = request.body
    ;(init as RequestInit & { duplex?: string }).duplex = "half"
  }

  // Use href string — some Edge fetch implementations drop URL.search on URL objects.
  const upstream = await fetch(target.href, init)
  const responseHeaders = new Headers()
  upstream.headers.forEach((value, key) => {
    if (HOP_BY_HOP.has(key.toLowerCase())) return
    responseHeaders.set(key, value)
  })

  if (request.method !== "GET" && request.method !== "HEAD") {
    responseHeaders.set("Cache-Control", "no-store")
  }

  // Temporary diagnostics for Tag Gateway verification (safe; no secrets).
  responseHeaders.set("X-Gtg-Upstream", `${target.pathname}${target.search}`)
  responseHeaders.set(
    "X-Gtg-Geo",
    headers.has("X-Forwarded-CountryRegion") || headers.has("X-Forwarded-Country")
      ? "1"
      : "0"
  )

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  })
}
