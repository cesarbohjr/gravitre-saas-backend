import { NextRequest } from "next/server"
import { proxyVoiceAudio } from "@/lib/voice-api-proxy"

export async function POST(request: NextRequest) {
  return proxyVoiceAudio(request, "/api/voice/preview")
}
