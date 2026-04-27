import type { SupabaseClient } from "@supabase/supabase-js"

type CountDiagnostics = {
  totalCount: number | null
  orgCount: number | null
  totalError: string | null
  orgError: string | null
}

export async function getOrgCountDiagnostics(
  supabase: SupabaseClient,
  table: string,
  orgId: string
): Promise<CountDiagnostics> {
  const [totalResult, orgResult] = await Promise.all([
    supabase.from(table).select("id", { count: "exact", head: true }),
    supabase.from(table).select("id", { count: "exact", head: true }).eq("org_id", orgId),
  ])

  return {
    totalCount: totalResult.count ?? null,
    orgCount: orgResult.count ?? null,
    totalError: totalResult.error?.message ?? null,
    orgError: orgResult.error?.message ?? null,
  }
}

export function isDebugRequest(searchParams: URLSearchParams): boolean {
  const raw = searchParams.get("debug")
  return raw === "1" || raw === "true"
}
