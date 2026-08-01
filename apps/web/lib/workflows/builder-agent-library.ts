/** Org agents for the workflow builder palette + agent-node bind. */

export type BuilderOrgAgent = {
  id: string
  name: string
  role?: string
  department?: string
  description?: string
  status?: string
  capabilities?: string[]
  lastAction?: string
  config?: Record<string, unknown> | null
}

export type BuilderAgentFilters = {
  query?: string
  department?: string
  role?: string
}

export function activeBuilderAgents(agents: BuilderOrgAgent[]): BuilderOrgAgent[] {
  const active = agents.filter((a) => !a.status || a.status === "active")
  return active.length > 0 ? active : agents
}

export function listAgentDepartments(agents: BuilderOrgAgent[]): string[] {
  const set = new Set<string>()
  for (const agent of activeBuilderAgents(agents)) {
    const dept = String(agent.department || "").trim()
    if (dept) set.add(dept)
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b))
}

export function listAgentRoles(agents: BuilderOrgAgent[]): string[] {
  const set = new Set<string>()
  for (const agent of activeBuilderAgents(agents)) {
    const role = String(agent.role || "").trim()
    if (role) set.add(role)
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b))
}

export function filterBuilderAgents(
  agents: BuilderOrgAgent[],
  filters: BuilderAgentFilters = {},
): BuilderOrgAgent[] {
  const q = String(filters.query || "")
    .trim()
    .toLowerCase()
  const department = String(filters.department || "")
    .trim()
    .toLowerCase()
  const role = String(filters.role || "")
    .trim()
    .toLowerCase()

  return activeBuilderAgents(agents).filter((agent) => {
    if (department && String(agent.department || "").toLowerCase() !== department) return false
    if (role && String(agent.role || "").toLowerCase() !== role) return false
    if (!q) return true
    const haystack = [
      agent.name,
      agent.role,
      agent.department,
      agent.description,
      agent.lastAction,
      ...(agent.capabilities || []),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
    return haystack.includes(q)
  })
}

export function agentNodeConfig(agent: BuilderOrgAgent): Record<string, unknown> {
  return {
    agent_id: agent.id,
    agentId: agent.id,
    task: agent.description || `Run as ${agent.name}`,
  }
}

export function agentLibrarySubtitle(agent: BuilderOrgAgent): string {
  const parts = [agent.role, agent.department].filter(Boolean)
  if (parts.length) return parts.join(" · ")
  if (agent.capabilities?.length) return agent.capabilities.slice(0, 2).join(", ")
  return "Org agent"
}

/** Extra tool / platform step presets backed by existing StepHandlers. */
export const BUILDER_TOOL_PRESETS: Array<{
  id: string
  name: string
  description: string
  nodeType: "tool" | "approval" | "task"
  config?: Record<string, unknown>
}> = [
  {
    id: "tool-rag",
    name: "Knowledge retrieve",
    description: "RAG retrieve from assigned knowledge",
    nodeType: "tool",
    config: { step_type: "rag_retrieve" },
  },
  {
    id: "tool-transform",
    name: "Transform data",
    description: "Map / reshape prior step outputs",
    nodeType: "tool",
    config: { step_type: "transform" },
  },
  {
    id: "tool-webhook",
    name: "Webhook",
    description: "HTTP POST to an external URL",
    nodeType: "tool",
    config: { step_type: "webhook_post" },
  },
  {
    id: "tool-email",
    name: "Send email",
    description: "Email send via connected mail",
    nodeType: "tool",
    config: { step_type: "email_send" },
  },
  {
    id: "tool-slack",
    name: "Post to Slack",
    description: "Slack message via connector",
    nodeType: "tool",
    config: { step_type: "slack_post_message" },
  },
  {
    id: "tool-sql",
    name: "SQL / data task",
    description: "Generic task node for data work",
    nodeType: "task",
  },
  {
    id: "tool-approval",
    name: "Approval gate",
    description: "Pause for human approval",
    nodeType: "approval",
  },
]
