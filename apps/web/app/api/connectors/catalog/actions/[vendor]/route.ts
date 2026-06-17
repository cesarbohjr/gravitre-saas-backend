import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

// G4: per-vendor action catalog passthrough.
export async function GET(request: NextRequest, { params }: { params: Promise<{ vendor: string }> }) {
  const { vendor } = await params
  return proxyToFastApi(request, `/api/connectors/catalog/actions/${encodeURIComponent(vendor)}`)
}
