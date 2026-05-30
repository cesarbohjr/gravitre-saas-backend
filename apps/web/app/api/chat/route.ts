import { NextRequest } from "next/server"

// Thin proxy: the assistant's AI logic lives entirely in the backend governance
// layer (backend/app/routers/assistant.py via model_router). This route only
// forwards the request (with the caller's JWT + org) and streams the backend's
// AI SDK UI message stream back to the browser. No AI SDK, no OpenAI, no tools,
// no prompts here.

export const maxDuration = 30

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

function resolveOrgId(req: NextRequest, bodyText: string): string {
  // Priority: request body → x-org-id header → query string.
  if (bodyText) {
    try {
      const parsed = JSON.parse(bodyText) as { org_id?: string }
      const fromBody = parsed.org_id?.trim()
      if (fromBody) return fromBody
    } catch {
      // Body may not be JSON during malformed requests.
    }
  }

  const fromHeader = req.headers.get("x-org-id")?.trim()
  if (fromHeader) return fromHeader

  const fromQuery = req.nextUrl.searchParams.get("org_id")?.trim()
  if (fromQuery) return fromQuery

  return ""
}

export async function POST(req: NextRequest) {
  const baseUrl = getBackendBaseUrl()
  if (!baseUrl) {
    return jsonError("AI assistant is not configured — FASTAPI_BASE_URL is not set", 503)
  }

  const body = await req.text()
  const auth = req.headers.get("authorization")
  const orgId = resolveOrgId(req, body)

  if (!orgId) {
    return jsonError("org_id is required", 400)
  }

  const headers: Record<string, string> = {
    "content-type": "application/json",
    accept: "text/event-stream",
    "x-org-id": orgId,
  }
  if (auth) headers.authorization = auth

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
      "Could not reach the AI backend — check your connection",
      502,
      error instanceof Error ? { detail: error.message } : undefined,
    )
  }

  // Non-streaming error from the backend (auth, killswitch, rate limit, etc.):
  // forward status + body so the client can surface the message.
  if (!upstream.ok || !upstream.body) {
    const text = await upstream.text().catch(() => "")
    return new Response(text || JSON.stringify({ error: "AI assistant request failed" }), {
      status: upstream.status || 502,
      headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" },
    })
  }

  // Stream the backend's UI message stream straight through to the browser.
  return new Response(upstream.body, {
    status: 200,
    headers: {
      "content-type": "text/event-stream",
      "cache-control": "no-cache",
      connection: "keep-alive",
      "x-vercel-ai-ui-message-stream": "v1",
      "x-accel-buffering": "no",
    },
  })
}
