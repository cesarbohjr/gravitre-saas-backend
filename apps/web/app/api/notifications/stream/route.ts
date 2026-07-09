import { NextRequest } from "next/server"

export const maxDuration = 300

function getBackendBaseUrl(): string | null {
  const value = process.env.FASTAPI_BASE_URL?.trim()
  return value ? value.replace(/\/+$/, "") : null
}

function jsonError(message: string, status: number) {
  return new Response(JSON.stringify({ error: message }), {
    status,
    headers: { "content-type": "application/json" },
  })
}

function fallbackSseResponse() {
  let interval: ReturnType<typeof setInterval> | undefined
  const stream = new ReadableStream({
    start(controller) {
      const encoder = new TextEncoder()
      controller.enqueue(encoder.encode("event: connected\ndata: {}\n\n"))
      interval = setInterval(() => {
        controller.enqueue(encoder.encode(": keepalive\n\n"))
      }, 25_000)
    },
    cancel() {
      if (interval) clearInterval(interval)
    },
  })

  return new Response(stream, {
    status: 200,
    headers: {
      "content-type": "text/event-stream",
      "cache-control": "no-cache",
      connection: "keep-alive",
      "x-accel-buffering": "no",
      "x-notification-stream": "fallback",
    },
  })
}

export async function GET(req: NextRequest) {
  const baseUrl = getBackendBaseUrl()
  if (!baseUrl) {
    return jsonError("Notification stream backend is not configured.", 503)
  }

  const auth = req.headers.get("authorization")
  if (!auth?.startsWith("Bearer ")) {
    return jsonError("Please sign in to receive live notifications", 401)
  }

  const headers: Record<string, string> = {
    accept: "text/event-stream",
    authorization: auth,
  }
  const orgId = req.headers.get("x-org-id")?.trim() || req.nextUrl.searchParams.get("org_id")?.trim()
  if (orgId) headers["x-org-id"] = orgId
  const environment = req.headers.get("x-environment")
  if (environment) headers["x-environment"] = environment

  const query = req.nextUrl.searchParams.toString()
  const target = `${baseUrl}/api/notifications/stream${query ? `?${query}` : ""}`

  let upstream: Response
  try {
    upstream = await fetch(target, {
      method: "GET",
      headers,
      cache: "no-store",
    })
  } catch (error) {
    return jsonError(
      error instanceof Error ? error.message : "Cannot reach notification stream backend",
      502,
    )
  }

  if (!upstream.ok || !upstream.body) {
    if (upstream.status === 404 || upstream.status === 405 || upstream.status === 501) {
      return fallbackSseResponse()
    }
    const text = await upstream.text().catch(() => "")
    return new Response(text || JSON.stringify({ error: "Notification stream failed" }), {
      status: upstream.status || 502,
      headers: { "content-type": upstream.headers.get("content-type") || "application/json" },
    })
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "content-type": "text/event-stream",
      "cache-control": "no-cache",
      connection: "keep-alive",
      "x-accel-buffering": "no",
    },
  })
}
