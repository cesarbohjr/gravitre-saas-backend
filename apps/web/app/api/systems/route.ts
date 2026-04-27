import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, getRouteClientAuthMode, resolveOrgId } from "@/lib/supabase/server"
import { ensureDemoDataForOrg } from "@/lib/supabase/demo-bootstrap"
import { getOrgCountDiagnostics, isDebugRequest } from "@/lib/supabase/route-diagnostics"
import { camelToSnake, snakeToCamel } from "@/lib/supabase/transforms"

export async function GET(request: NextRequest) {
  try {
    const debugEnabled = isDebugRequest(request.nextUrl.searchParams)
    const authMode = getRouteClientAuthMode(request)
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }
    await ensureDemoDataForOrg(supabase, orgId)
    const diagnostics = await getOrgCountDiagnostics(supabase, "connected_systems", orgId)
    const { data, error } = await supabase
      .from("connected_systems")
      .select("*")
      .eq("org_id", orgId)
      .order("created_at", { ascending: false })
    if (error) {
      return NextResponse.json(
        {
          error: error.message,
          ...(debugEnabled
            ? {
                _debug: {
                  resolvedOrgId: orgId,
                  table: "connected_systems",
                  ...diagnostics,
                  authMode,
                },
              }
            : {}),
        },
        { status: 500 }
      )
    }
    if ((data ?? []).length === 0) {
      console.warn("Systems route returned empty result", {
        orgId,
        diagnostics,
        authMode,
      })
    }
    return NextResponse.json({
      systems: (data ?? []).map((row) => snakeToCamel<Record<string, unknown>>(row)),
      ...(debugEnabled
        ? {
            _debug: {
              resolvedOrgId: orgId,
              table: "connected_systems",
              ...diagnostics,
              queryError: null,
              authMode,
            },
          }
        : {}),
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }
    const body = await request.json()
    const snake = camelToSnake(body as Record<string, unknown>)
    const payload = {
      org_id: orgId,
      system_key: String(snake.system_key ?? snake.name ?? "system"),
      name: String(snake.name ?? "Connected System"),
      type: String(snake.type ?? "custom"),
      status: String(snake.status ?? "connected"),
      config: (snake.config as Record<string, unknown> | undefined) ?? {},
    }
    const { data, error } = await supabase
      .from("connected_systems")
      .insert(payload)
      .select("*")
      .single()
    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }
    return NextResponse.json({ system: snakeToCamel<Record<string, unknown>>(data) }, { status: 201 })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
