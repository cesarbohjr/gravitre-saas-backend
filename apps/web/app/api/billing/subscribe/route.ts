import { NextRequest, NextResponse } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"
import { createSupabaseServerClient } from "@/lib/supabase-server"

const JSON_HEADERS = { "content-type": "application/json; charset=utf-8" } as const

export async function POST(request: NextRequest) {
  const headers = new Headers(request.headers)
  const incomingAuth = request.headers.get("authorization")

  if (!incomingAuth?.startsWith("Bearer ")) {
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

    if (!session?.access_token) {
      return NextResponse.json(
        { error: "Unauthorized", detail: "No session token" },
        { status: 401, headers: JSON_HEADERS },
      )
    }

    headers.set("authorization", `Bearer ${session.access_token}`)
  }

  const body = await request.text()
  if (body && !headers.has("content-type")) {
    headers.set("content-type", "application/json")
  }

  return proxyToFastApi(
    new NextRequest(request.url, { method: "POST", headers, body: body || undefined }),
    "/api/billing/subscribe",
  )
}
