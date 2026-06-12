import { NextRequest, NextResponse } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"
import { buildDemoOperatorPlan } from "@/lib/demo-operator-plan"
import { getDemoStore } from "@/lib/demo-runtime-store"

interface RouteParams {
  params: Promise<{ id: string }>
}

export async function POST(request: NextRequest, { params }: RouteParams) {
  const { id } = await params
  const rawBody = await request.text()
  const body = (JSON.parse(rawBody || "{}") || {}) as { task?: string }
  const task = String(body.task ?? "Investigate issue").trim()

  if (process.env.FASTAPI_BASE_URL?.trim()) {
    const proxiedRequest = new NextRequest(request.url, {
      method: request.method,
      headers: request.headers,
      body: rawBody,
    })
    const upstream = await proxyToFastApi(proxiedRequest, `/api/sessions/${id}/task`)
    if (upstream.ok) return upstream
    if (upstream.status !== 404 && upstream.status < 500) return upstream
  }

  const session = getDemoStore().sessions.find((item) => item.id === id)
  if (session) {
    session.status = "running"
  }

  return NextResponse.json(buildDemoOperatorPlan(task))
}
