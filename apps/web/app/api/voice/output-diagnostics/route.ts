import { NextRequest } from "next/server"
import { proxyVoiceJson } from "@/lib/voice-api-proxy"

/**
 * Browser playback telemetry proxy.
 *
 * The client posts to the same-origin Next.js API. Without this route the
 * request 404s before reaching FastAPI, which makes physical-output evidence
 * look empty even when the browser is emitting playback diagnostics.
 */
export async function POST(request: NextRequest) {
  return proxyVoiceJson(request, "/api/voice/output-diagnostics")
}
