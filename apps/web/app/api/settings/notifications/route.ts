import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"
import { ensureDemoDataForOrg } from "@/lib/supabase/demo-bootstrap"

function defaultNotifications() {
  return {
    emailEnabled: false,
    slackEnabled: false,
    recipients: [] as string[],
  }
}

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
      .select("settings")
      .eq("id", orgId)
      .maybeSingle()

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    const settings = (data?.settings as Record<string, unknown> | null) ?? {}
    const incoming = (settings.notificationPreferences as Record<string, unknown> | undefined) ?? {}
    const notifications = {
      emailEnabled: Boolean(incoming.emailEnabled ?? incoming.email),
      slackEnabled: Boolean(incoming.slackEnabled ?? incoming.slack),
      recipients: Array.isArray(incoming.recipients)
        ? incoming.recipients.map((value) => String(value))
        : [],
    }

    return NextResponse.json({ notifications })
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
    await ensureDemoDataForOrg(supabase, orgId)

    const body = await request.json().catch(() => ({}))
    const nextNotifications = {
      emailEnabled: Boolean(body?.emailEnabled),
      slackEnabled: Boolean(body?.slackEnabled),
      recipients: Array.isArray(body?.recipients) ? body.recipients.map((value: unknown) => String(value)) : [],
    }

    const { data: orgData, error: orgError } = await supabase
      .from("organizations")
      .select("settings")
      .eq("id", orgId)
      .maybeSingle()

    if (orgError) {
      return NextResponse.json({ error: orgError.message }, { status: 500 })
    }

    const currentSettings = (orgData?.settings as Record<string, unknown> | null) ?? {}
    const mergedSettings = {
      ...currentSettings,
      notificationPreferences: nextNotifications,
    }

    const { error: updateError } = await supabase
      .from("organizations")
      .update({
        settings: mergedSettings,
      })
      .eq("id", orgId)

    if (updateError) {
      return NextResponse.json({ error: updateError.message }, { status: 500 })
    }

    return NextResponse.json({ notifications: nextNotifications ?? defaultNotifications() })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
