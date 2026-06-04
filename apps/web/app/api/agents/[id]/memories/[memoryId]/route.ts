import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

interface RouteParams {
  params: Promise<{ id: string; memoryId: string }>
}

export async function GET(request: NextRequest, { params }: RouteParams) {
  const { id, memoryId } = await params
  return proxyToFastApi(request, `/api/agents/${id}/memories/${memoryId}`)
}

export async function PATCH(request: NextRequest, { params }: RouteParams) {
  const { id, memoryId } = await params
  return proxyToFastApi(request, `/api/agents/${id}/memories/${memoryId}`)
}

export async function DELETE(request: NextRequest, { params }: RouteParams) {
  const { id, memoryId } = await params
  return proxyToFastApi(request, `/api/agents/${id}/memories/${memoryId}`)
}
