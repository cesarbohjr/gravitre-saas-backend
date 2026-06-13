import { NextRequest, NextResponse } from "next/server"
import { createSupabaseServerClient } from "@/lib/supabase-server"

const JSON_HEADERS = { "content-type": "application/json; charset=utf-8" } as const
const TIMEOUT_MS = 10_000

const STATUS_MESSAGES: Record<number, string> = {
  401: "Authentication required",
  403: "You do not have permission to modify this workflow run",
  404: "Workflow run not found",
  409: "This run cannot be modified in its current state",
  503: "Backend unavailable — please try again",
  504: "Request timed out — the backend did not respond in time",
}

async function resolveBearerToken(request: NextRequest): Promise<string | null> {
  const auth = request.headers.get("authorization")?.trim()
  if (auth?.toLowerCase().startsWith("bearer ")) {
    return auth
  }
  try {
    const supabase = await createSupabaseServerClient()
    const { data } = await supabase.auth.getSession()
    const token = data.session?.access_token
    return token ? `Bearer ${token}` : null
  } catch {
    return null
  }
}

function mapRunActionError(status: number, payload: unknown) {
  const error = STATUS_MESSAGES[status] ?? "Request failed"
  if (payload && typeof payload === "object") {
    return NextResponse.json({ ...(payload as object), error }, { status, headers: JSON_HEADERS })
  }
  return NextResponse.json({ error }, { status, headers: JSON_HEADERS })
}

/**
 * Proxy workflow run mutations (cancel/retry/rollback) to FastAPI.
 * Returns mapped errors for common status codes; 10s upstream timeout.
 */
export async function proxyRunAction(request: NextRequest, runId: string, action: string) {
  const bearer = await resolveBearerToken(request)
  if (!bearer) {
    return NextResponse.json({ error: "Authentication required" }, { status: 401, headers: JSON_HEADERS })
  }

  const baseUrl = process.env.FASTAPI_BASE_URL?.trim()?.replace(/\/+$/, "")
  if (!baseUrl) {
    return NextResponse.json(
      { error: "Backend not configured — FASTAPI_BASE_URL is not set" },
      { status: 503, headers: JSON_HEADERS },
    )
  }

  const body = await request.text()
  const headers = new Headers({
    authorization: bearer,
    accept: "application/json",
  })
  const contentType = request.headers.get("content-type")
  if (contentType) headers.set("content-type", contentType)
  const xOrgId = request.headers.get("x-org-id")
  if (xOrgId) headers.set("x-org-id", xOrgId)
  const xEnv = request.headers.get("x-environment")
  if (xEnv) headers.set("x-environment", xEnv)

  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS)

  try {
    const upstream = await fetch(`${baseUrl}/api/runs/${runId}/${action}`, {
      method: "POST",
      headers,
      body: body || undefined,
      cache: "no-store",
      signal: controller.signal,
    })
    clearTimeout(timeout)

    const contentTypeHeader = upstream.headers.get("content-type") ?? ""
    const payload = contentTypeHeader.includes("application/json") ? await upstream.json() : null

    if (upstream.ok) {
      if (payload === null) return new NextResponse(null, { status: upstream.status })
      return NextResponse.json(payload, { status: upstream.status, headers: JSON_HEADERS })
    }

    if (upstream.status in STATUS_MESSAGES) {
      return mapRunActionError(upstream.status, payload)
    }

    if (payload !== null) {
      return NextResponse.json(payload, { status: upstream.status, headers: JSON_HEADERS })
    }
    return NextResponse.json({ error: "Request failed" }, { status: upstream.status, headers: JSON_HEADERS })
  } catch (error) {
    clearTimeout(timeout)
    if (error instanceof Error && error.name === "AbortError") {
      return mapRunActionError(504, null)
    }
    return mapRunActionError(503, { detail: error instanceof Error ? error.message : "Unknown proxy error" })
  }
}

/** Proxy per-step workflow run mutations to FastAPI. */
export async function proxyRunStepAction(
  request: NextRequest,
  runId: string,
  stepId: string,
  action: string,
) {
  const bearer = await resolveBearerToken(request)
  if (!bearer) {
    return NextResponse.json({ error: "Authentication required" }, { status: 401, headers: JSON_HEADERS })
  }

  const baseUrl = process.env.FASTAPI_BASE_URL?.trim()?.replace(/\/+$/, "")
  if (!baseUrl) {
    return NextResponse.json(
      { error: "Backend not configured — FASTAPI_BASE_URL is not set" },
      { status: 503, headers: JSON_HEADERS },
    )
  }

  const body = await request.text()
  const headers = new Headers({
    authorization: bearer,
    accept: "application/json",
  })
  const contentType = request.headers.get("content-type")
  if (contentType) headers.set("content-type", contentType)
  const xOrgId = request.headers.get("x-org-id")
  if (xOrgId) headers.set("x-org-id", xOrgId)
  const xEnv = request.headers.get("x-environment")
  if (xEnv) headers.set("x-environment", xEnv)

  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS)

  try {
    const upstream = await fetch(`${baseUrl}/api/runs/${runId}/steps/${stepId}/${action}`, {
      method: "POST",
      headers,
      body: body || undefined,
      cache: "no-store",
      signal: controller.signal,
    })
    clearTimeout(timeout)

    const contentTypeHeader = upstream.headers.get("content-type") ?? ""
    const payload = contentTypeHeader.includes("application/json") ? await upstream.json() : null

    if (upstream.ok) {
      if (payload === null) return new NextResponse(null, { status: upstream.status })
      return NextResponse.json(payload, { status: upstream.status, headers: JSON_HEADERS })
    }

    if (upstream.status in STATUS_MESSAGES) {
      return mapRunActionError(upstream.status, payload)
    }

    if (payload !== null) {
      return NextResponse.json(payload, { status: upstream.status, headers: JSON_HEADERS })
    }
    return NextResponse.json({ error: "Request failed" }, { status: upstream.status, headers: JSON_HEADERS })
  } catch (error) {
    clearTimeout(timeout)
    if (error instanceof Error && error.name === "AbortError") {
      return mapRunActionError(504, null)
    }
    return mapRunActionError(503, { detail: error instanceof Error ? error.message : "Unknown proxy error" })
  }
}
