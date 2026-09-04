import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ id: string }> },
) {
  const { id } = await context.params
  const qs = request.nextUrl.search || ""
  return proxyToFastApi(request, `/api/work-objects/${id}${qs}`)
}
