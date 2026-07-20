import { NextRequest, NextResponse } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"
import { shouldUseDemoRuntimeFallback } from "@/lib/demo-runtime-fallback"
import { addSession, getDemoStore } from "@/lib/demo-runtime-store"

function isProxyEnabled(): boolean {
  return Boolean(process.env.FASTAPI_BASE_URL?.trim())
}

export async function GET(request: NextRequest) {
  if (isProxyEnabled()) {
    const upstream = await proxyToFastApi(request, "/api/sessions")
    if (upstream.ok || upstream.status < 500) return upstream
  }
  if (shouldUseDemoRuntimeFallback()) {
    return NextResponse.json({ sessions: getDemoStore().sessions })
  }
  return NextResponse.json(
    { sessions: [], error: "Backend unavailable", detail: "FASTAPI_BASE_URL is not configured" },
    { status: 503 },
  )
}

export async function POST(request: NextRequest) {
  if (isProxyEnabled()) {
    const upstream = await proxyToFastApi(request, "/api/sessions")
    if (upstream.ok || upstream.status < 500) return upstream
  }

  if (!shouldUseDemoRuntimeFallback()) {
    return NextResponse.json(
      { error: "Backend unavailable", detail: "FASTAPI_BASE_URL is not configured" },
      { status: 503 },
    )
  }

  const body = (await request.json().catch(() => ({}))) as { title?: string }
  const title = String(body.title ?? "").trim() || "New Operator Session"
  const session = addSession(title)
  return NextResponse.json({ session }, { status: 201 })
}
