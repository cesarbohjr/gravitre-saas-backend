import { NextRequest } from "next/server"

// Thin proxy: the assistant's AI logic lives entirely in the backend governance
// layer (backend/app/routers/assistant.py via model_router). This route only
// forwards the request (with the caller's JWT + org) and streams the backend's
// AI SDK UI message stream back to the browser.

// Assistant pipeline (retrieval + ReAct + follow-up chips) can exceed 30s on tool-heavy turns.
export const maxDuration = 120

function getBackendBaseUrl(): string | null {
  const value = process.env.FASTAPI_BASE_URL?.trim()
  return value ? value.replace(/\/+$/, "") : null
}

function jsonError(message: string, status: number, extra?: Record<string, string>) {
  return new Response(JSON.stringify({ error: message, ...extra }), {
    status,
    headers: { "content-type": "application/json" },
  })
}

function mapUpstreamError(status: number, bodyText: string): Response {
  let detail = bodyText.trim()
  try {
    const parsed = JSON.parse(bodyText) as { detail?: unknown; error?: unknown }
    if (typeof parsed.detail === "string" && parsed.detail) detail = parsed.detail
    else if (typeof parsed.error === "string" && parsed.error) detail = parsed.error
  } catch {
    // keep raw text
  }

  if (status === 401) {
    return jsonError("Please sign in again to continue", 401)
  }
  if (status === 402) {
    return jsonError("AI credit limit reached — check billing", 402)
  }
  if (status === 403) {
    return jsonError(detail || "You don't have access to this organization", 403)
  }
  if (status === 429) {
    return jsonError("Too many requests — wait a moment", 429)
  }
  if (status === 503) {
    return jsonError("AI service is starting up, try again", 503)
  }
  if (status >= 500) {
    return jsonError("AI assistant is temporarily unavailable", status)
  }

  return new Response(JSON.stringify({ error: detail || "AI assistant request failed" }), {
    status,
    headers: { "content-type": "application/json" },
  })
}

function resolveOrgId(req: NextRequest): string {
  const fromHeader = req.headers.get("x-org-id")?.trim()
  if (fromHeader) return fromHeader

  const fromQuery = req.nextUrl.searchParams.get("org_id")?.trim()
  if (fromQuery) return fromQuery

  return ""
}

export async function POST(req: NextRequest) {
  const baseUrl = getBackendBaseUrl()
  if (!baseUrl) {
    return jsonError("AI backend is not configured. Contact support.", 503)
  }

  const auth = req.headers.get("authorization")
  if (!auth?.startsWith("Bearer ")) {
    return jsonError("Please sign in to use the AI assistant", 401)
  }

  const body = await req.text()
  const orgId = resolveOrgId(req)

  const headers: Record<string, string> = {
    "content-type": "application/json",
    accept: "text/event-stream",
    authorization: auth,
  }
  if (orgId) headers["x-org-id"] = orgId
  const environment = req.headers.get("x-environment")
  if (environment) headers["x-environment"] = environment

  let upstream: Response
  try {
    upstream = await fetch(`${baseUrl}/api/assistant/chat`, {
      method: "POST",
      headers,
      body,
      cache: "no-store",
    })
  } catch (error) {
    return jsonError(
      "Cannot reach the AI backend. Check your internet connection.",
      502,
      error instanceof Error ? { detail: error.message } : undefined,
    )
  }

  if (!upstream.ok || !upstream.body) {
    const text = await upstream.text().catch(() => "")
    return mapUpstreamError(upstream.status || 502, text)
  }

  const responseHeaders: Record<string, string> = {
    "content-type": "text/event-stream",
    "cache-control": "no-cache",
    connection: "keep-alive",
    "x-vercel-ai-ui-message-stream": "v1",
    "x-accel-buffering": "no",
  }
  const conversationId = upstream.headers.get("x-conversation-id")
  if (conversationId) {
    responseHeaders["x-conversation-id"] = conversationId
  }

  return new Response(upstream.body, {
    status: 200,
    headers: responseHeaders,
  })
}
