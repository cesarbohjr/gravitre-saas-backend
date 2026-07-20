import { NextRequest, NextResponse } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"
import { shouldUseDemoRuntimeFallback } from "@/lib/demo-runtime-fallback"
import { getDemoStore } from "@/lib/demo-runtime-store"
import { isDemoApprovalId } from "@/lib/demo-approval-ids"

export async function GET(request: NextRequest) {
  if (process.env.FASTAPI_BASE_URL?.trim()) {
    return proxyToFastApi(request, "/api/approvals")
  }

  if (shouldUseDemoRuntimeFallback()) {
    return NextResponse.json({ approvals: getDemoStore().approvals })
  }

  // Fail closed — never fabricate approvals for real orgs when backend is unset.
  return NextResponse.json(
    { approvals: [], error: "Backend unavailable", detail: "FASTAPI_BASE_URL is not configured" },
    { status: 503 },
  )
}
