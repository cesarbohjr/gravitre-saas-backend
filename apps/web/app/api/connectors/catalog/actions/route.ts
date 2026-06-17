import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

// G4: proxy the connector action catalog (v1 read / v2 write / v3 advanced + demo
// workflows) so the connectors UI can show real action readiness per vendor.
export async function GET(request: NextRequest) {
  return proxyToFastApi(request, "/api/connectors/catalog/actions")
}
