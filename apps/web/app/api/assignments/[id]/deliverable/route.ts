import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params
  return proxyToFastApi(request, `/api/agent-jobs/${id}/deliverable`)
}
