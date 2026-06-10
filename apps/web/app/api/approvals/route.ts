import { NextRequest, NextResponse } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"
import { getDemoStore } from "@/lib/demo-runtime-store"

export async function GET(request: NextRequest) {
  if (process.env.FASTAPI_BASE_URL?.trim()) {
    const upstream = await proxyToFastApi(request, "/api/approvals")
    if (upstream.ok || upstream.status < 500) {
      return upstream
    }
  }

  return NextResponse.json({ approvals: getDemoStore().approvals })
}
