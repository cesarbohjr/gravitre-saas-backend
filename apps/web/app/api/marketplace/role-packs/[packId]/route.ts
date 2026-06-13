import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

type RouteContext = { params: Promise<{ packId: string }> }

export async function GET(request: NextRequest, context: RouteContext) {
  const { packId } = await context.params
  return proxyToFastApi(request, `/api/marketplace/role-packs/${packId}`)
}
