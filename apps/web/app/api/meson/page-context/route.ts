import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

export async function GET(request: NextRequest) {
  const qs = request.nextUrl.searchParams.toString()
  return proxyToFastApi(request, `/api/meson/page-context${qs ? `?${qs}` : ""}`)
}
