import { NextRequest, NextResponse } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

export async function GET(request: NextRequest) {
  if (process.env.FASTAPI_BASE_URL?.trim()) {
    return proxyToFastApi(request, "/api/approvals/delegates")
  }
  return NextResponse.json(
    { delegates: [], detail: "Backend unavailable", error: "FASTAPI_BASE_URL is not configured" },
    { status: 503 },
  )
}
