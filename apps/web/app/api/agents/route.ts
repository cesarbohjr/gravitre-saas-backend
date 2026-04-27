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

    const diagnostics = await getOrgCountDiagnostics(supabase, "agents", orgId)
    const { data, error } = await supabase
      .from("agents")
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
                  table: "agents",
                  ...diagnostics,
                  authMode,
                },
              }
            : {}),
        },
        { status: 500 }
      )
    }

    const agents = (data ?? []).map((row) => {
      const model = snakeToCamel<Record<string, unknown>>(row)
      return {
        id: String(model.id),
        name: String(model.name ?? "Agent"),
        role: String(model.role ?? model.name ?? "AI Agent"),
        department: "Operations",
        description: String(model.description ?? model.purpose ?? "AI teammate"),
        status: String(model.status ?? "idle"),
        personality: {
          color: "blue",
          gradient: "from-blue-500 to-indigo-500",
          glow: "shadow-blue-500/30",
        },
        stats: {
          tasksToday: 0,
          successRate: 100,
          avgResponseTime: "-",
          workflowsUsing: 0,
        },
        capabilities: Array.isArray(model.capabilities) ? model.capabilities : [],
        permissions: Array.isArray(model.systems) ? model.systems : [],
        lastAction: "No recent activity",
        lastActionTime: "recently",
      }
    })

    if ((data ?? []).length === 0) {
      console.warn("Agents route returned empty result", {
        orgId,
        diagnostics,
        authMode,
      })
    }

    return NextResponse.json({
      agents,
      operators: agents,
      ...(debugEnabled
        ? {
            _debug: {
              resolvedOrgId: orgId,
              table: "agents",
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
    const { data: userData } = await supabase.auth.getUser()

    const insertPayload = {
      org_id: orgId,
      name: String(snake.name ?? "New Agent"),
      purpose: (snake.purpose as string | undefined) ?? null,
      role: (snake.role as string | undefined) ?? String(snake.name ?? "New Agent"),
      model: (snake.model as string | undefined) ?? "auto",
      description:
        (snake.description as string | undefined) ??
        (snake.purpose as string | undefined) ??
        null,
      capabilities: Array.isArray(snake.capabilities) ? snake.capabilities : [],
      systems: Array.isArray(snake.systems) ? snake.systems : [],
      guardrails: Array.isArray(snake.guardrails) ? snake.guardrails : [],
      status: "active",
      created_by: userData.user?.id ?? null,
    }

    const { data, error } = await supabase
      .from("agents")
      .insert(insertPayload)
      .select("*")
      .single()

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json(snakeToCamel<Record<string, unknown>>(data), { status: 201 })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
