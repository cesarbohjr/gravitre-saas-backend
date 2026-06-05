import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

interface RouteParams {
  params: Promise<{ provider: string }>
}

export async function POST(request: NextRequest, { params }: RouteParams) {
  const { provider } = await params
  return proxyToFastApi(request, `/api/connectors/oauth/${provider}/start`)
}
