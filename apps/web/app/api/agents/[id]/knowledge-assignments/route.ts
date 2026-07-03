import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

interface RouteParams {
  params: Promise<{ id: string }>
}

export async function GET(request: NextRequest, { params }: RouteParams) {
  const { id } = await params
  return proxyToFastApi(request, `/api/agents/${id}/knowledge-assignments`)
}

export async function POST(request: NextRequest, { params }: RouteParams) {
  const { id } = await params
  return proxyToFastApi(request, `/api/agents/${id}/knowledge-assignments`)
}
