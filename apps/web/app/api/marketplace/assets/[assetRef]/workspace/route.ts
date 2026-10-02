import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"
export async function GET(request: NextRequest, context: { params: Promise<{ assetRef: string }> }) {
  const { assetRef } = await context.params
  return proxyToFastApi(request, `/api/marketplace/assets/${encodeURIComponent(assetRef)}/workspace`)
}
