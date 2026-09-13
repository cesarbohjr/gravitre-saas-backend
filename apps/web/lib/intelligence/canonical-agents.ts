import type { Agent, AgentDepartment, AgentStatus } from "@/types/api"

/** Canonical agent row from GET /api/intelligence/page-context snapshot.agents */
export type CanonicalAgentRow = {
  id: string
  name: string
  role?: string | null
  department?: string | null
  businessLabel: string
  configuredStatus: string
  executionStatus: string
  isConfiguredActive: boolean
  isCurrentlyRunning: boolean
}

function parseConfiguredStatus(raw: string): AgentStatus {
  const normalized = raw.toLowerCase()
  if (normalized === "active") return "active"
  if (normalized === "processing" || normalized === "running") return "processing"
  if (normalized === "error" || normalized === "failed") return "error"
  return "idle"
}

const DEPARTMENTS = new Set<string>([
  "Marketing",
  "Sales",
  "Operations",
  "Finance",
  "Support",
  "HR",
  "Customer Success",
  "Engineering",
  "Security",
  "General",
])

function mapDepartment(raw: string | null | undefined): AgentDepartment {
  if (!raw) return "General"
  const titled = raw.trim().replace(/\b\w/g, (c) => c.toUpperCase())
  if (DEPARTMENTS.has(titled)) return titled as AgentDepartment
  const lower = raw.toLowerCase()
  if (lower.includes("sales")) return "Sales"
  if (lower.includes("marketing")) return "Marketing"
  if (lower.includes("finance")) return "Finance"
  if (lower.includes("support")) return "Support"
  if (lower.includes("hr") || lower.includes("talent")) return "HR"
  return "General"
}

/** Map canonical roster rows to Agent stubs for the intelligence map topology. */
export function canonicalAgentsToMapAgents(rows: CanonicalAgentRow[] | undefined): Agent[] {
  if (!rows?.length) return []
  return rows.map((row) => {
    const configured = parseConfiguredStatus(row.configuredStatus)
    const status: AgentStatus =
      row.isCurrentlyRunning && configured !== "error" ? "processing" : configured
    return {
      id: row.id,
      name: row.businessLabel || row.name,
      role: row.role ?? "Agent",
      department: mapDepartment(row.department),
      description: "",
      status,
      personality: {
        color: "#6366f1",
        gradient: "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
        glow: "rgba(99, 102, 241, 0.35)",
      },
      stats: {
        tasksToday: 0,
        successRate: null,
        avgResponseTime: "—",
        workflowsUsing: 0,
      },
      capabilities: [],
      permissions: [],
      lastAction: row.isCurrentlyRunning ? "Running" : status,
      lastActionTime: "",
    }
  })
}
