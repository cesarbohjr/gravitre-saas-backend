"use client"

import { useMemo } from "react"
import useSWR from "swr"
import { agentsApi } from "@/lib/api"

/**
 * Department of an agent known only by id or name (assignment cards, run
 * subtasks), read from GET /api/agents. Shares one cached request across
 * every surface that calls it.
 */
export function useAgentDepartments(): (agent: { id?: string | null; name?: string | null }) => string | null {
  const { data } = useSWR("agent-departments", () => agentsApi.list(), { revalidateOnFocus: false })
  return useMemo(() => {
    const byId = new Map<string, string>()
    const byName = new Map<string, string>()
    for (const a of data?.agents ?? []) {
      if (!a.department) continue
      byId.set(a.id, a.department)
      if (a.name) byName.set(a.name.trim().toLowerCase(), a.department)
    }
    return ({ id, name }) =>
      (id ? byId.get(id) : undefined) ?? (name ? byName.get(name.trim().toLowerCase()) : undefined) ?? null
  }, [data])
}
