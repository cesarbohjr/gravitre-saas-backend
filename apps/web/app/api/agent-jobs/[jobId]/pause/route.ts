import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

interface RouteParams {
  params: Promise<{ jobId: string }>
}

export async function POST(request: NextRequest, { params }: RouteParams) {
  const { jobId } = await params
  return proxyToFastApi(request, `/api/agent-jobs/${jobId}/pause`)
}
