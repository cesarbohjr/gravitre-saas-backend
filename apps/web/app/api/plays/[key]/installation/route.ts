import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

export async function GET(request: NextRequest, context: { params: Promise<{ key: string }> }) {
  const { key } = await context.params
  return proxyToFastApi(request, `/api/plays/${encodeURIComponent(key)}/installation`)
}

export async function PUT(request: NextRequest, context: { params: Promise<{ key: string }> }) {
  const { key } = await context.params
  return proxyToFastApi(request, `/api/plays/${encodeURIComponent(key)}/installation`)
}
