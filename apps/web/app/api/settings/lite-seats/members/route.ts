import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

export async function POST(request: NextRequest) {
  return proxyToFastApi(request, "/api/settings/lite-seats/members")
}

export async function DELETE(request: NextRequest) {
  return proxyToFastApi(request, "/api/settings/lite-seats/members")
}
