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
      .from("workflows")
      .select("*")
      .eq("org_id", orgId)
      .order("created_at", { ascending: false })

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    const workflows = (data ?? []).map((row) => {
      const model = snakeToCamel<Record<string, unknown>>(row)
      return {
        ...model,
        runCount: Number(model.runCount ?? 0),
        successRate: `${Number(model.successRate ?? 0).toFixed(1)}%`,
        lastRun: model.updatedAt ?? null,
      }
    })

    return NextResponse.json({ workflows })
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

    const { data, error } = await supabase
      .from("workflows")
      .insert({
        org_id: orgId,
        name: String(snake.name ?? "New Workflow"),
        description: (snake.description as string | undefined) ?? null,
        status: (snake.status as string | undefined) ?? "draft",
        environment: (snake.environment as string | undefined) ?? "production",
        nodes: Array.isArray(snake.nodes) ? snake.nodes : [],
        edges: Array.isArray(snake.edges) ? snake.edges : [],
        config: (snake.config as Record<string, unknown> | undefined) ?? {},
      })
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
