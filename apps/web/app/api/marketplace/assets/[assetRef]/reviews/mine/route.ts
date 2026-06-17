import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

type RouteContext = { params: Promise<{ assetRef: string }> }

export async function PUT(request: NextRequest, context: RouteContext) {
  const { assetRef } = await context.params
  return proxyToFastApi(request, `/api/marketplace/assets/${encodeURIComponent(assetRef)}/reviews/mine`)
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  const { assetRef } = await context.params
  return proxyToFastApi(request, `/api/marketplace/assets/${encodeURIComponent(assetRef)}/reviews/mine`)
}
