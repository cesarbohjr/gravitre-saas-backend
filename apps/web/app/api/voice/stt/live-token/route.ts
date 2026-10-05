import { NextRequest, NextResponse } from "next/server"
import { proxyVoiceJson } from "@/lib/voice-api-proxy"

export async function POST(request: NextRequest) {
  if (process.env.PLAYWRIGHT_E2E === "1") {
    return NextResponse.json({
      ws_url: "wss://api.deepgram.com/v1/listen?model=nova-2",
      access_token: "harness-token",
      authorization: "Bearer harness-token",
      expires_in_seconds: 60,
      encoding: "linear16",
      sample_rate: 16000,
      provider: "deepgram",
    })
  }
  return proxyVoiceJson(request, "/api/voice/stt/live-token", { method: "POST", body: "{}" })
}
