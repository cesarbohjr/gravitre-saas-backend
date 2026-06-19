import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

export async function GET(request: NextRequest) {
  const url = new URL(request.url)
  const query = url.searchParams.toString()
  const suffix = query ? `?${query}` : ""
  return proxyToFastApi(request, `/api/marketplace/platform/catalog${suffix}`)
}
