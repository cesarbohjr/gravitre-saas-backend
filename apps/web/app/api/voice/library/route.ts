import { NextRequest } from "next/server"
import { proxyVoiceJson } from "@/lib/voice-api-proxy"

export async function GET(request: NextRequest) {
  const search = request.nextUrl.search || ""
  return proxyVoiceJson(request, "/api/voice/library", { method: "GET", search })
}
