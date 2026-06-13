import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

export async function GET(request: NextRequest) {
  const workflowId = request.nextUrl.searchParams.get("workflowId")
  const suffix = workflowId ? `?workflow_id=${encodeURIComponent(workflowId)}` : ""
  return proxyToFastApi(request, `/api/meson/feedback/metrics${suffix}`)
}
