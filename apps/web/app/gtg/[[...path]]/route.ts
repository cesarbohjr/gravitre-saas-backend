import type { NextRequest } from "next/server"

import { MARKETING_GTG_FPS_HOST } from "@/lib/marketing-gtm"
import {
  applyTagGatewayGeoHeaders,
  buildTagGatewayUpstreamUrl,
} from "@/lib/marketing-gtg-proxy"

export const runtime = "edge"
export const dynamic = "force-dynamic"

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

type RouteContext = {
  params: Promise<{ path?: string[] }>
}

async function proxyToTagGateway(request: NextRequest, context: RouteContext): Promise<Response> {
  const { path: segments } = await context.params
  // nextUrl keeps query params reliable on Vercel Edge (request.url alone can drop them).
  const target = buildTagGatewayUpstreamUrl(request.nextUrl, segments)

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

export const GET = proxyToTagGateway
export const HEAD = proxyToTagGateway
export const POST = proxyToTagGateway
export const PUT = proxyToTagGateway
export const PATCH = proxyToTagGateway
export const DELETE = proxyToTagGateway
export const OPTIONS = proxyToTagGateway
