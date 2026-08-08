import { NextRequest, NextResponse } from "next/server"
import { backendBaseUrl } from "@/lib/public-urls"

export function voiceFastApiBase(): string {
  const configured = process.env.FASTAPI_BASE_URL?.trim()
  if (configured) return backendBaseUrl().replace(/\/+$/, "")
  return "http://localhost:8000"
}

export function forwardAuthHeaders(request: NextRequest, *, accept?: string): Headers {
  const headers = new Headers()
  const auth = request.headers.get("authorization")
  const org = request.headers.get("x-org-id")
  const env = request.headers.get("x-environment")
  if (auth) headers.set("authorization", auth)
  if (org) headers.set("x-org-id", org)
  if (env) headers.set("x-environment", env)
  if (accept) headers.set("accept", accept)
  return headers
}

export async function proxyVoiceJson(
  request: NextRequest,
  path: string,
  init?: { method?: string; body?: string | null; search?: string },
): Promise<NextResponse> {
  const base = voiceFastApiBase()
  const method = init?.method || request.method
  const headers = forwardAuthHeaders(request)
  if (method !== "GET" && method !== "HEAD") {
    headers.set("content-type", "application/json")
  }
  const url = `${base}${path}${init?.search || ""}`
  const upstream = await fetch(url, {
    method,
    headers,
    body: method === "GET" || method === "HEAD" ? undefined : init?.body ?? (await request.text()),
    cache: "no-store",
  })
  const text = await upstream.text()
  try {
    const json = JSON.parse(text)
    return NextResponse.json(json, { status: upstream.status })
  } catch {
    return new NextResponse(text, {
      status: upstream.status,
      headers: { "content-type": upstream.headers.get("content-type") || "text/plain" },
    })
  }
}

export async function proxyVoiceAudio(
  request: NextRequest,
  path: string,
): Promise<NextResponse> {
  const base = voiceFastApiBase()
  const headers = forwardAuthHeaders(request, { accept: "audio/mpeg" })
  headers.set("content-type", "application/json")
  const body = await request.text()
  const upstream = await fetch(`${base}${path}`, {
    method: "POST",
    headers,
    body,
    cache: "no-store",
  })
  if (!upstream.ok) {
    const detail = await upstream.text()
    return NextResponse.json(
      { error: "Voice audio failed", detail: detail.slice(0, 800) },
      { status: upstream.status },
    )
  }
  const audio = await upstream.arrayBuffer()
  return new NextResponse(audio, {
    status: 200,
    headers: {
      "content-type": upstream.headers.get("content-type") || "audio/mpeg",
      "cache-control": "no-store",
      "x-voice-latency-ms": upstream.headers.get("x-voice-latency-ms") || "",
    },
  })
}
