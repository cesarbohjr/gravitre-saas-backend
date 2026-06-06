import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ registryId: string }> }
) {
  const { registryId } = await params
  return proxyToFastApi(request, `/api/marketplace/billing/pricing/${registryId}`)
}
