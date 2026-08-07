import { NextRequest, NextResponse } from "next/server"
import { backendBaseUrl } from "@/lib/public-urls"

function getFastApiBaseUrl() {
  const configured = process.env.FASTAPI_BASE_URL?.trim()
  if (configured) return backendBaseUrl()
  return "http://localhost:8000"
}

export async function POST(request: NextRequest) {
  const base = getFastApiBaseUrl().replace(/\/+$/, "")
  const headers = new Headers()
  const auth = request.headers.get("authorization")
  const org = request.headers.get("x-org-id")
  const env = request.headers.get("x-environment")
  const contentType = request.headers.get("content-type")
  if (auth) headers.set("authorization", auth)
  if (org) headers.set("x-org-id", org)
  if (env) headers.set("x-environment", env)
  if (contentType) headers.set("content-type", contentType)

  const body = await request.arrayBuffer()
  const upstream = await fetch(`${base}/api/voice/stt`, {
    method: "POST",
    headers,
    body,
    cache: "no-store",
  })

  const text = await upstream.text()
  let payload: unknown = text
  try {
    payload = text ? JSON.parse(text) : null
  } catch {
    payload = { detail: text }
  }
  return NextResponse.json(payload, { status: upstream.status })
}
