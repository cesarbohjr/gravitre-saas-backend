import { NextRequest, NextResponse } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"
import { shouldUseDemoRuntimeFallback } from "@/lib/demo-runtime-fallback"
import { getDemoStore } from "@/lib/demo-runtime-store"

interface RouteParams {
  params: Promise<{ id: string }>
}

export async function GET(request: NextRequest, { params }: RouteParams) {
  const { id } = await params
  if (process.env.FASTAPI_BASE_URL?.trim()) {
    const upstream = await proxyToFastApi(request, `/api/sessions/${id}`)
    if (upstream.ok || upstream.status < 500) return upstream
  }

  if (!shouldUseDemoRuntimeFallback()) {
    return NextResponse.json(
      { detail: "Backend unavailable", error: "FASTAPI_BASE_URL is not configured" },
      { status: 503 },
    )
  }

  const session = getDemoStore().sessions.find((item) => item.id === id)
  if (!session) {
    return NextResponse.json({ detail: "Session not found" }, { status: 404 })
  }
  return NextResponse.json({ session })
}
