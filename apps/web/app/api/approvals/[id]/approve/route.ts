import { NextRequest, NextResponse } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"
import { setApprovalStatus } from "@/lib/demo-runtime-store"

interface RouteParams {
  params: Promise<{ id: string }>
}

export async function POST(request: NextRequest, { params }: RouteParams) {
  const { id } = await params
  if (process.env.FASTAPI_BASE_URL?.trim()) {
    const upstream = await proxyToFastApi(request, `/api/approvals/${id}/approve`)
    if (upstream.ok || upstream.status < 500) {
      return upstream
    }
  }

  const updated = setApprovalStatus(id, "approved")
  if (!updated) {
    return NextResponse.json({ detail: "Approval not found" }, { status: 404 })
  }
  return NextResponse.json({ run: { id, approval_status: "approved", status: "running" } })
}
