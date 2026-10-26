"use client"

import { useMemo } from "react"
import useSWR from "swr"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import {
  normalizeAgentsPayload,
  rosterStatsKey,
  toRosterAgent,
  type RosterAgent,
  type RosterStatsPayload,
} from "@/lib/agents-roster"
import type { AgentDepartmentId } from "@/components/agents/fleet-v4/types"

/**
 * Live agent counts for status chips on Workspace pages: the same
 * /api/agents and /api/metrics/agent-roster data the Agents roster uses.
 * Counts stay null until both have loaded, so a chip never shows a guess.
 */
export function useWorkforce(): {
  agents: RosterAgent[] | null
  working: number | null
  byDepartment: (dept: AgentDepartmentId) => number | null
} {
  const { user } = useAuth()
  const { data } = useSWR(user ? "/api/agents" : null, apiFetcher, { dedupingInterval: 5000 })
  const statsKey = useMemo(() => (user ? rosterStatsKey() : null), [user])
  const { data: stats, error: statsError } = useSWR<RosterStatsPayload>(statsKey, apiFetcher, { dedupingInterval: 5000 })
  const agents = useMemo(
    () => (data ? normalizeAgentsPayload(data).map((raw) => toRosterAgent(raw, stats && !statsError ? stats : undefined)) : null),
    [data, stats, statsError],
  )
  const working = agents && stats && !statsError ? agents.filter((a) => a.state === "working").length : null
  return {
    agents,
    working,
    byDepartment: (dept) => (agents ? agents.filter((a) => a.department === dept).length : null),
  }
}
