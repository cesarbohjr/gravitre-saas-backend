import type { NextRequest } from "next/server"

import { proxyTagGatewayRequest } from "@/lib/marketing-gtg-proxy"

export const runtime = "edge"
export const dynamic = "force-dynamic"

type RouteContext = {
  params: Promise<{ path: string[] }>
}

/** /gtg/* subpaths (e.g. /gtg/healthy, /gtg/ns.html). */
async function handle(request: NextRequest, context: RouteContext): Promise<Response> {
  const { path } = await context.params
  return proxyTagGatewayRequest(request, path)
}

export const GET = handle
export const HEAD = handle
export const POST = handle
export const PUT = handle
export const PATCH = handle
export const DELETE = handle
export const OPTIONS = handle
