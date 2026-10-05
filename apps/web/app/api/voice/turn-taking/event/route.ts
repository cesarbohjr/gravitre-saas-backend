import { NextRequest, NextResponse } from "next/server"
import { proxyVoiceJson } from "@/lib/voice-api-proxy"

export async function POST(request: NextRequest) {
  if (process.env.PLAYWRIGHT_E2E === "1") {
    return NextResponse.json({ state: {}, finalized_transcript: "hello harness" })
  }
  return proxyVoiceJson(request, "/api/voice/turn-taking/event")
}
