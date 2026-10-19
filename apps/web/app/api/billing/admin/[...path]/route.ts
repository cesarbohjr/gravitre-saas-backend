import { NextRequest, NextResponse } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

const UUID = /^[0-9a-f-]{36}$/i

const isAllowed = (segments: string[], method: string) => {
  if (method === "GET") return (segments.length === 1 && ["billing-safety", "promotion-codes"].includes(segments[0])) || segments[0] === "commercial-accounts" && (
    segments.length === 1 || (segments.length === 3 && UUID.test(segments[1]) && segments[2] === "stripe")
  )
  if (method !== "POST") return false
  if (segments.length === 1) return ["customer-segments", "promotional-offers", "billing-reconciliation", "promotion-codes"].includes(segments[0])
  if (segments.length !== 3 || !UUID.test(segments[1])) return false
  return (segments[0] === "promotional-offers" && ["revoke", "release"].includes(segments[2])) ||
    (segments[0] === "promotion-codes" && segments[2] === "deactivate")
}

async function handle(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params
  if (!isAllowed(path, request.method)) return NextResponse.json({ detail: "Not found" }, { status: 404 })
  const target = `/api/billing/admin/${path.join("/")}`
  return proxyToFastApi(request, target)
}

export const GET = handle
export const POST = handle
