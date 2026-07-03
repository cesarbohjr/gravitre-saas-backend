import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

interface RouteParams {
  params: Promise<{ id: string; assignmentId: string }>
}

export async function PATCH(request: NextRequest, { params }: RouteParams) {
  const { id, assignmentId } = await params
  return proxyToFastApi(request, `/api/agents/${id}/knowledge-assignments/${assignmentId}`)
}

export async function DELETE(request: NextRequest, { params }: RouteParams) {
  const { id, assignmentId } = await params
  return proxyToFastApi(request, `/api/agents/${id}/knowledge-assignments/${assignmentId}`)
}
