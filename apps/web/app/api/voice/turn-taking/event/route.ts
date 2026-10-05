import { NextRequest } from "next/server"
import { proxyVoiceJson } from "@/lib/voice-api-proxy"

export async function POST(request: NextRequest) {
  return proxyVoiceJson(request, "/api/voice/turn-taking/event")
}
