import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

export async function GET(request: NextRequest) {
  const qs = request.nextUrl.search || ""
  return proxyToFastApi(request, `/api/work-objects${qs}`)
}
