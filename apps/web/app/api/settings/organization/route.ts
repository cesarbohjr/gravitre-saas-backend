import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"
import { ensureDemoDataForOrg } from "@/lib/supabase/demo-bootstrap"
import { camelToSnake, snakeToCamel } from "@/lib/supabase/transforms"

export async function GET(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }
    await ensureDemoDataForOrg(supabase, orgId)

    const { data, error } = await supabase
      .from("organizations")
      .select("*")
      .eq("id", orgId)
      .maybeSingle()

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({
      organization: data ? snakeToCamel<Record<string, unknown>>(data) : null,
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}

export async function PATCH(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const body = await request.json()
    const snake = camelToSnake(body as Record<string, unknown>)

    const { data, error } = await supabase
      .from("organizations")
      .update({
        name: snake.name ?? null,
        slug: snake.slug ?? null,
        primary_domain: snake.primary_domain ?? snake.primaryDomain ?? null,
        logo_url: snake.logo_url ?? snake.logoUrl ?? null,
      })
      .eq("id", orgId)
      .select("*")
      .single()

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ organization: snakeToCamel<Record<string, unknown>>(data) })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
