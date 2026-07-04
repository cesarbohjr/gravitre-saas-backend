import { NextRequest, NextResponse } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"
import { getDemoStore } from "@/lib/demo-runtime-store"
import { isDemoApprovalId } from "@/lib/demo-approval-ids"

export async function GET(request: NextRequest) {
  if (process.env.FASTAPI_BASE_URL?.trim()) {
    return proxyToFastApi(request, "/api/approvals")
  }

  return NextResponse.json({ approvals: getDemoStore().approvals })
}
