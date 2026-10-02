import { NextRequest, NextResponse } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"
type Context = { params: Promise<{ assetRef: string; action: string }> }
export async function GET(request: NextRequest, context: Context) {
  const { assetRef, action } = await context.params
  if (action !== "blueprint") return NextResponse.json({ detail: "Not found" }, { status: 404 })
  return proxyToFastApi(request, `/api/marketplace/platform/assets/${encodeURIComponent(assetRef)}/marketplace3/blueprint`)
}
export async function POST(request: NextRequest, context: Context) {
  const { assetRef, action } = await context.params
  if (!["install-pilot", "certify", "certify-run", "promote"].includes(action)) return NextResponse.json({ detail: "Not found" }, { status: 404 })
  return proxyToFastApi(request, `/api/marketplace/platform/assets/${encodeURIComponent(assetRef)}/marketplace3/${action}`)
}
