import { NextRequest, NextResponse } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"
import { shouldUseDemoRuntimeFallback } from "@/lib/demo-runtime-fallback"
import { setApprovalStatus } from "@/lib/demo-runtime-store"
import { isDemoApprovalId } from "@/lib/demo-approval-ids"

interface RouteParams {
  params: Promise<{ id: string }>
}

export async function POST(request: NextRequest, { params }: RouteParams) {
  const { id } = await params

  if (isDemoApprovalId(id) && shouldUseDemoRuntimeFallback()) {
    const updated = setApprovalStatus(id, "rejected")
    if (!updated) {
      return NextResponse.json({ detail: "Approval not found" }, { status: 404 })
    }
    return NextResponse.json({ run: { id, approval_status: "rejected", status: "cancelled" } })
  }

  if (process.env.FASTAPI_BASE_URL?.trim()) {
    const upstream = await proxyToFastApi(request, `/api/approvals/${id}/reject`)
    if (upstream.ok || upstream.status < 500) {
      return upstream
    }
  }

  if (shouldUseDemoRuntimeFallback() && isDemoApprovalId(id)) {
    const updated = setApprovalStatus(id, "rejected")
    if (!updated) {
      return NextResponse.json({ detail: "Approval not found" }, { status: 404 })
    }
    return NextResponse.json({ run: { id, approval_status: "rejected", status: "cancelled" } })
  }

  return NextResponse.json(
    { detail: "Backend unavailable", error: "FASTAPI_BASE_URL is not configured" },
    { status: 503 },
  )
}
