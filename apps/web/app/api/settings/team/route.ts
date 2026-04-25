import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

export async function GET(request: NextRequest) {
  return proxyToFastApi(request, "/api/org/members")
}

export async function POST(request: NextRequest) {
  return proxyToFastApi(request, "/api/org/members/invite")
}
