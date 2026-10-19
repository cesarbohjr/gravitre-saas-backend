import { NextRequest, NextResponse } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

const isAllowed = (segments: string[], method: string) => {
  if (method === "GET") return (segments.length === 1 && segments[0] === "billing-safety") || segments[0] === "commercial-accounts" && (
    segments.length === 1 || (segments.length === 3 && /^[0-9a-f-]{36}$/i.test(segments[1]) && segments[2] === "stripe")
  )
  if (method !== "POST") return false
  if (segments.length === 1) return ["customer-segments", "promotional-offers", "billing-reconciliation"].includes(segments[0])
  return segments.length === 3 && segments[0] === "promotional-offers" &&
    /^[0-9a-f-]{36}$/i.test(segments[1]) && segments[2] === "revoke"
}

async function handle(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params
  if (!isAllowed(path, request.method)) return NextResponse.json({ detail: "Not found" }, { status: 404 })
  const target = `/api/billing/admin/${path.join("/")}`
  return proxyToFastApi(request, target)
}

export const GET = handle
export const POST = handle
