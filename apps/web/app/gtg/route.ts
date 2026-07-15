import type { NextRequest } from "next/server"

import { proxyTagGatewayRequest } from "@/lib/marketing-gtg-proxy"

export const runtime = "edge"
export const dynamic = "force-dynamic"

/** Exact /gtg (loader + validate_geo). Kept separate from [...path] so query strings are not dropped. */
async function handle(request: NextRequest): Promise<Response> {
  return proxyTagGatewayRequest(request, null)
}

export const GET = handle
export const HEAD = handle
export const POST = handle
export const PUT = handle
export const PATCH = handle
export const DELETE = handle
export const OPTIONS = handle
