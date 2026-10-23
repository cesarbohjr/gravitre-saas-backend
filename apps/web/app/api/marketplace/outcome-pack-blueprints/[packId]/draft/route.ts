import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"
type Context = { params: Promise<{ packId: string }> }
export async function POST(request: NextRequest, context: Context) {
  const { packId } = await context.params
  return proxyToFastApi(request, `/api/marketplace/outcome-pack-blueprints/${encodeURIComponent(packId)}/draft`)
}
