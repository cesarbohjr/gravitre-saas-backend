import { NextRequest, NextResponse } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

export async function GET(request: NextRequest) {
  if (process.env.FASTAPI_BASE_URL?.trim()) {
    return proxyToFastApi(request, "/api/goals/templates")
  }
  return NextResponse.json(
    { templates: [], detail: "Backend unavailable", error: "FASTAPI_BASE_URL is not configured" },
    { status: 503 },
  )
}
