import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

interface RouteParams {
  params: Promise<{ id: string; assignmentId: string }>
}

export async function POST(request: NextRequest, { params }: RouteParams) {
  const { id, assignmentId } = await params
  return proxyToFastApi(request, `/api/agents/${id}/knowledge-assignments/${assignmentId}/sync`)
}
