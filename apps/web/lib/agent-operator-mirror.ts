import { mapAgentStatusToOperator } from "@/lib/agent-display"

type SupabaseClient = {
  from: (table: string) => {
    upsert: (
      payload: Record<string, unknown>,
      options: { onConflict: string },
    ) => PromiseLike<{ error: { message: string } | null }>
  }
}

export async function syncOperatorMirror(
  supabase: SupabaseClient,
  orgId: string,
  agentRow: Record<string, unknown>,
  userId: string | null,
) {
  const agentId = String(agentRow.id ?? "")
  if (!agentId) return

  const operatorPayload: Record<string, unknown> = {
    id: agentId,
    org_id: orgId,
    name: String(agentRow.name ?? "Agent"),
    description:
      (agentRow.description as string | null | undefined) ??
      (agentRow.purpose as string | null | undefined) ??
      null,
    role: (agentRow.role as string | null | undefined) ?? String(agentRow.name ?? "Agent"),
    status: mapAgentStatusToOperator(String(agentRow.status ?? "active")),
    capabilities: Array.isArray(agentRow.capabilities) ? agentRow.capabilities : [],
    config: agentRow.config && typeof agentRow.config === "object" ? agentRow.config : {},
    icon: agentRow.icon ?? null,
    avatar_color: agentRow.avatar_color ?? agentRow.avatarColor ?? null,
    avatar_url: agentRow.avatar_url ?? agentRow.avatarUrl ?? null,
    updated_at: new Date().toISOString(),
  }
  if (userId) {
    operatorPayload.created_by = userId
  }

  const { error } = await supabase.from("operators").upsert(operatorPayload, { onConflict: "id" })
  if (error) {
    console.warn("[agents] operator mirror upsert failed:", error.message)
  }
}
