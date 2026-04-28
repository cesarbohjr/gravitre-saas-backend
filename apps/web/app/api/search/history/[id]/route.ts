import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

interface RouteParams {
  params: Promise<{ id: string }>
}

export async function DELETE(request: NextRequest, { params }: RouteParams) {
  const { id } = await params
  return proxyToFastApi(request, `/api/search/history/${id}`)
}
