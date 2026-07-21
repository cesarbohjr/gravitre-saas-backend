import { NextRequest, NextResponse } from "next/server"
import { backendBaseUrl } from "@/lib/public-urls"

const JSON_HEADERS = { "content-type": "application/json; charset=utf-8" } as const
const METHODS_WITH_BODY = new Set(["POST", "PUT", "PATCH", "DELETE"])

function getFastApiBaseUrl() {
  // Prefer Railway prod when FASTAPI_BASE_URL is unset or still points at api.gravitre.app
  // before DNS is live. Local dev falls back to localhost when nothing is configured.
  const configured = process.env.FASTAPI_BASE_URL?.trim()
  if (configured) {
    return backendBaseUrl()
  }
  return "http://localhost:8000"
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
    const text = await response.text()
    if (!text.trim()) return null
    try {
      return JSON.parse(text) as unknown
    } catch {
      return { detail: text }
    }
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

/** STA-271 C.2: best-effort mirror of contract workflow row into legacy workflow_defs. */
export async function syncWorkflowSchemaFromContract(request: NextRequest, workflowId: string) {
  if (!process.env.FASTAPI_BASE_URL?.trim()) {
    return
  }
  try {
    const baseUrl = getFastApiBaseUrl()
    const targetUrl = buildBackendUrl(
      baseUrl,
      `/api/workflows/${encodeURIComponent(workflowId)}/schema-sync/from-contract`,
      request
    )
    await fetch(targetUrl, {
      method: "POST",
      headers: forwardHeaders(request),
      cache: "no-store",
    })
  } catch {
    // UI write already succeeded; execution sync can be retried from builder/API.
  }
}
