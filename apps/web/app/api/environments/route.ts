import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

export async function GET(request: NextRequest) {
  return proxyToFastApi(request, "/api/environments")
}

export async function POST(request: NextRequest) {
  return proxyToFastApi(request, "/api/environments")
}
