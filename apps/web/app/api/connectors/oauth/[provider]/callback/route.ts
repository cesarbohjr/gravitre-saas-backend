import { NextRequest } from "next/server"

import { completeConnectorOAuthCallback } from "@/lib/connector-oauth-callback"

interface RouteParams {
  params: Promise<{ provider: string }>
}

export async function GET(request: NextRequest, { params }: RouteParams) {
  const { provider } = await params
  return completeConnectorOAuthCallback(request, provider)
}
