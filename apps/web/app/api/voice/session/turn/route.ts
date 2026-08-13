import { NextRequest, NextResponse } from "next/server"
import { forwardAuthHeaders, voiceFastApiBase } from "@/lib/voice-api-proxy"

/** NDJSON proxy for full-duplex voice session turns (same CognitiveTurnKernel path). */
export async function POST(request: NextRequest) {
  const base = voiceFastApiBase()
  const headers = forwardAuthHeaders(request, { accept: "application/x-ndjson" })
  headers.set("content-type", "application/json")
  const body = await request.text()
  const upstream = await fetch(`${base}/api/voice/session/turn`, {
    method: "POST",
    headers,
    body,
    cache: "no-store",
  })
  if (!upstream.ok || !upstream.body) {
    const detail = await upstream.text()
    return NextResponse.json(
      { error: "Voice session turn failed", detail: detail.slice(0, 800) },
      { status: upstream.status },
    )
  }
  return new NextResponse(upstream.body, {
    status: 200,
    headers: {
      "content-type": upstream.headers.get("content-type") || "application/x-ndjson",
      "cache-control": "no-store",
      "x-voice-session": "1",
      "x-originating-modality": "voice",
      "x-write-confirm-policy":
        upstream.headers.get("x-write-confirm-policy") || "nl_yes_same_path_as_text",
    },
  })
}
