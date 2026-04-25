import { NextRequest, NextResponse } from "next/server"

const JSON_HEADERS = { "content-type": "application/json; charset=utf-8" } as const
const METHODS_WITH_BODY = new Set(["POST", "PUT", "PATCH", "DELETE"])

function getFastApiBaseUrl() {
  const value = process.env.FASTAPI_BASE_URL?.trim()
  if (!value) {
    throw new Error("FASTAPI_BASE_URL is not set")
  }
  return value.replace(/\/+$/, "")
}

function buildBackendUrl(baseUrl: string, backendPath: string, request: NextRequest) {
  const normalizedPath = backendPath.startsWith("/") ? backendPath : `/${backendPath}`
  const url = new URL(`${baseUrl}${normalizedPath}`)
  request.nextUrl.searchParams.forEach((value, key) => {
    url.searchParams.set(key, value)
  })
  return url.toString()
}

function toJsonResponse(payload: unknown, status: number) {
  return new NextResponse(JSON.stringify(payload), {
    status,
    headers: JSON_HEADERS,
  })
}

async function safeReadPayload(response: Response) {
  const contentType = response.headers.get("content-type") ?? ""
  if (contentType.includes("application/json")) {
    return response.json()
  }

  const text = await response.text()
  return text ? { detail: text } : null
}

function forwardHeaders(request: NextRequest) {
  const headers = new Headers()
  const auth = request.headers.get("authorization")
  const contentType = request.headers.get("content-type")
  const accept = request.headers.get("accept")
  const xOrgId = request.headers.get("x-org-id")
  const xEnv = request.headers.get("x-environment")

  if (auth) headers.set("authorization", auth)
  if (contentType) headers.set("content-type", contentType)
  if (accept) headers.set("accept", accept)
  if (xOrgId) headers.set("x-org-id", xOrgId)
  if (xEnv) headers.set("x-environment", xEnv)

  return headers
}

export async function proxyToFastApi(request: NextRequest, backendPath: string) {
  let baseUrl: string
  try {
    baseUrl = getFastApiBaseUrl()
  } catch (error) {
    return toJsonResponse(
      {
        error: "Server configuration error",
        detail: error instanceof Error ? error.message : "FASTAPI_BASE_URL missing",
      },
      500
    )
  }

  const targetUrl = buildBackendUrl(baseUrl, backendPath, request)
  const init: RequestInit = {
    method: request.method,
    headers: forwardHeaders(request),
    cache: "no-store",
  }

  if (METHODS_WITH_BODY.has(request.method.toUpperCase())) {
    const body = await request.text()
    if (body) {
      init.body = body
    }
  }

  try {
    const upstream = await fetch(targetUrl, init)
    const payload = await safeReadPayload(upstream)

    if (payload === null) {
      return new NextResponse(null, { status: upstream.status })
    }

    return toJsonResponse(payload, upstream.status)
  } catch (error) {
    return toJsonResponse(
      {
        error: "Backend request failed",
        detail: error instanceof Error ? error.message : "Unknown proxy error",
      },
      502
    )
  }
}
