import { NextRequest, NextResponse } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"
import { createSupabaseServerClient } from "@/lib/supabase-server"

const JSON_HEADERS = { "content-type": "application/json; charset=utf-8" } as const

export async function GET(request: NextRequest) {
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
    return NextResponse.json({ error: "Unauthorized" }, { status: 401, headers: JSON_HEADERS })
  }

  const headers = new Headers(request.headers)
  headers.set("authorization", bearer)

  return proxyToFastApi(
    new NextRequest(request.url, { method: "GET", headers }),
    "/api/billing",
  )
}

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
    return NextResponse.json({ error: "Unauthorized" }, { status: 401, headers: JSON_HEADERS })
  }

  const headers = new Headers(request.headers)
  headers.set("authorization", bearer)

  return proxyToFastApi(request, "/api/billing")
}
