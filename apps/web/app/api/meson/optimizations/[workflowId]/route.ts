import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

interface RouteParams {
  params: Promise<{ workflowId: string }>
}

export async function GET(request: NextRequest, { params }: RouteParams) {
  const { workflowId } = await params
  return proxyToFastApi(request, `/api/meson/optimizations/${workflowId}`)
}
