import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

export async function GET(request: NextRequest) {
  return proxyToFastApi(request, "/api/settings/lite-seats")
}

export async function POST(request: NextRequest) {
  return proxyToFastApi(request, "/api/settings/lite-seats")
}

export async function PATCH(request: NextRequest) {
  return proxyToFastApi(request, "/api/settings/lite-seats")
}

export async function DELETE(request: NextRequest) {
  return proxyToFastApi(request, "/api/settings/lite-seats")
}

