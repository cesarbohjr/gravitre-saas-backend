import { apiFetch } from "@/lib/fetcher"

export const GOALS_REFRESH_KEY = "goals-list"

export type GoalStatus = "draft" | "active" | "paused" | "completed" | "cancelled"

export interface GoalRecord {
  id: string
  objective: string
  category?: string | null
  priority?: string | null
  frequency?: string | null
  department?: string | null
  status: GoalStatus
  connectedSystems?: string[]
  successMetrics?: Record<string, unknown>
  createdAt?: string
  updatedAt?: string
}

export async function fetchGoalList(): Promise<GoalRecord[]> {
  const response = await apiFetch("/api/goals")
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { error?: string }
    throw new Error(body.error ?? `Failed to load goals (${response.status})`)
  }
  const payload = (await response.json()) as { goals?: GoalRecord[] }
  return Array.isArray(payload.goals) ? payload.goals : []
}
