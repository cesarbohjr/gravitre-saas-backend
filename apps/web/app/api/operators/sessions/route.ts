import { NextRequest, NextResponse } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"
import { addSession, getDemoStore } from "@/lib/demo-runtime-store"

function isProxyEnabled(): boolean {
  return Boolean(process.env.FASTAPI_BASE_URL?.trim())
}

export async function GET(request: NextRequest) {
  if (isProxyEnabled()) {
    const upstream = await proxyToFastApi(request, "/api/sessions")
    if (upstream.ok || upstream.status < 500) return upstream
  }
  return NextResponse.json({ sessions: getDemoStore().sessions })
}

export async function POST(request: NextRequest) {
  if (isProxyEnabled()) {
    const upstream = await proxyToFastApi(request, "/api/sessions")
    if (upstream.ok || upstream.status < 500) return upstream
  }

  const body = (await request.json().catch(() => ({}))) as { title?: string }
  const title = String(body.title ?? "").trim() || "New Operator Session"
  const session = addSession(title)
  return NextResponse.json({ session }, { status: 201 })
}
