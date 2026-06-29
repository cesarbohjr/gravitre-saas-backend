import { NextRequest, NextResponse } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"
import { createSupabaseServerClient } from "@/lib/supabase-server"

const JSON_HEADERS = { "content-type": "application/json; charset=utf-8" } as const

export async function POST(request: NextRequest) {
  const supabase = await createSupabaseServerClient()
  const {
    data: { user },
    error: userError,
  } = await supabase.auth.getUser()

  if (userError || !user) {
    return NextResponse.json(
      { error: "Unauthorized", detail: userError?.message ?? "No session" },
      { status: 401, headers: JSON_HEADERS },
    )
  }

  const {
    data: { session },
  } = await supabase.auth.getSession()

  const accessToken = session?.access_token
  const authHeader = request.headers.get("authorization")
  const bearer =
    authHeader?.startsWith("Bearer ") ? authHeader : accessToken ? `Bearer ${accessToken}` : null

  if (!bearer) {
    return NextResponse.json(
      { error: "Unauthorized", detail: "No session token" },
      { status: 401, headers: JSON_HEADERS },
    )
  }

  const body = await request.text()
  const headers = new Headers(request.headers)
  headers.set("authorization", bearer)
  if (body && !headers.has("content-type")) {
    headers.set("content-type", "application/json")
  }

  return proxyToFastApi(
    new NextRequest(request.url, { method: "POST", headers, body: body || undefined }),
    "/api/billing/checkout",
  )
}
