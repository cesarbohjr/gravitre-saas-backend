import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

export async function GET(request: NextRequest) {
  return proxyToFastApi(request, "/api/settings/memory-entity-embeddings")
}

export async function PUT(request: NextRequest) {
  return proxyToFastApi(request, "/api/settings/memory-entity-embeddings")
}
