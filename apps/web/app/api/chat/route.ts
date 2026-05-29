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

function jsonError(message: string, status: number, detail?: string) {
  return new Response(JSON.stringify({ error: message, ...(detail ? { detail } : {}) }), {
    status,
    headers: { "content-type": "application/json" },
  })
}

export async function POST(req: NextRequest) {
  const baseUrl = getBackendBaseUrl()
  if (!baseUrl) {
    return jsonError("AI assistant is not configured", 503, "FASTAPI_BASE_URL is not set")
  }

  const body = await req.text()
  const auth = req.headers.get("authorization")
  const orgId = req.headers.get("x-org-id")

  const headers: Record<string, string> = {
    "content-type": "application/json",
    accept: "text/event-stream",
  }
  if (auth) headers.authorization = auth
  if (orgId) headers["x-org-id"] = orgId

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
      "AI assistant backend is unreachable",
      502,
      error instanceof Error ? error.message : "proxy error",
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
