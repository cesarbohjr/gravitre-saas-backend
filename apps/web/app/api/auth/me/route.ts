import { NextRequest, NextResponse } from "next/server"

import { proxyToFastApi } from "@/lib/backend-proxy"
import { createClient } from "@/lib/supabase/server"

const JSON_HEADERS = { "content-type": "application/json; charset=utf-8" } as const

/** Minimal profile when Supabase session is valid but Railway JWT validation fails. */
function fallbackMeFromSupabase(user: {
  id: string
  email?: string | null
  created_at?: string
}) {
  return {
    user_id: user.id,
    org_id: null,
    email: user.email ?? null,
    role: null,
    user: {
      id: user.id,
      email: user.email ?? null,
      full_name: null,
      avatar_url: null,
      role: null,
      created_at: user.created_at ?? null,
      updated_at: null,
    },
    organizations: [],
    current_org: null,
    onboarding: { seeded: false, completed_at: null, checklist_dismissed: false },
    billing: {
      status: "trialing",
      plan_code: "node",
      can_access_app: true,
    },
    _auth_degraded: true,
  }
}

export async function GET(request: NextRequest) {
  const supabase = await createClient()
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
    return NextResponse.json(fallbackMeFromSupabase(user), {
      status: 200,
      headers: JSON_HEADERS,
    })
  }

  const headers = new Headers(request.headers)
  headers.set("authorization", bearer)

  const proxied = await proxyToFastApi(
    new NextRequest(request.url, { method: "GET", headers }),
    "/api/auth/me",
  )

  if (proxied.status === 401) {
    console.warn(
      "[api/auth/me] Backend rejected JWT for user=%s — returning Supabase fallback",
      user.email ?? user.id,
    )
    return NextResponse.json(fallbackMeFromSupabase(user), {
      status: 200,
      headers: JSON_HEADERS,
    })
  }

  return proxied
}

export async function PATCH(request: NextRequest) {
  const supabase = await createClient()
  const {
    data: { session },
  } = await supabase.auth.getSession()

  if (!session?.access_token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401, headers: JSON_HEADERS })
  }

  const headers = new Headers(request.headers)
  headers.set("authorization", `Bearer ${session.access_token}`)

  return proxyToFastApi(
    new NextRequest(request.url, {
      method: "PATCH",
      headers,
      body: await request.text(),
    }),
    "/api/auth/me",
  )
}
