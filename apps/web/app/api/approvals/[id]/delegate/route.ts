import { NextRequest, NextResponse } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

interface RouteParams {
  params: Promise<{ id: string }>
}

export async function POST(request: NextRequest, { params }: RouteParams) {
  const { id } = await params
  if (process.env.FASTAPI_BASE_URL?.trim()) {
    return proxyToFastApi(request, `/api/approvals/${encodeURIComponent(id)}/delegate`)
  }
  return NextResponse.json(
    { detail: "Backend unavailable", error: "FASTAPI_BASE_URL is not configured" },
    { status: 503 },
  )
}
