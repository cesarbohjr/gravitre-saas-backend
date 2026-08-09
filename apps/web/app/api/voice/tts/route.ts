import { NextRequest, NextResponse } from "next/server"
import { backendBaseUrl } from "@/lib/public-urls"

function getFastApiBaseUrl() {
  const configured = process.env.FASTAPI_BASE_URL?.trim()
  if (configured) return backendBaseUrl()
  return "http://localhost:8000"
}

export async function POST(request: NextRequest) {
  const base = getFastApiBaseUrl().replace(/\/+$/, "")
  const headers = new Headers()
  const auth = request.headers.get("authorization")
  const org = request.headers.get("x-org-id")
  const env = request.headers.get("x-environment")
  const qaVoice = request.headers.get("x-gravitre-qa-force-voice-error")
  if (auth) headers.set("authorization", auth)
  if (org) headers.set("x-org-id", org)
  if (env) headers.set("x-environment", env)
  if (qaVoice) headers.set("X-Gravitre-QA-Force-Voice-Error", qaVoice)
  headers.set("content-type", "application/json")
  headers.set("accept", "audio/mpeg")

  const body = await request.text()
  const upstream = await fetch(`${base}/api/voice/tts`, {
    method: "POST",
    headers,
    body,
    cache: "no-store",
  })

  if (!upstream.ok) {
    const detailText = await upstream.text()
    // Prefer structured FastAPI detail so clients can read error_class/billing_issue.
    try {
      const parsed = JSON.parse(detailText) as unknown
      return NextResponse.json(
        { error: "TTS failed", ...(typeof parsed === "object" && parsed ? parsed : { detail: detailText }) },
        { status: upstream.status },
      )
    } catch {
      return NextResponse.json(
        { error: "TTS failed", detail: detailText.slice(0, 800) },
        { status: upstream.status },
      )
    }
  }

  const audio = await upstream.arrayBuffer()
  return new NextResponse(audio, {
    status: 200,
    headers: {
      "content-type": upstream.headers.get("content-type") || "audio/mpeg",
      "cache-control": "no-store",
      "x-voice-provider": upstream.headers.get("x-voice-provider") || "",
      "x-voice-key": upstream.headers.get("x-voice-key") || "",
      "x-voice-latency-ms": upstream.headers.get("x-voice-latency-ms") || "",
    },
  })
}
