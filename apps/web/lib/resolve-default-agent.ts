/**
 * STA-321 — resolve org agents for pack-driven surfaces so consumers are not
 * forced through a manual "choose agent" step (chat already auto-routes).
 */

export type ResolvableAgent = {
  id: string
  name?: string
  role?: string
  status?: string
  config?: Record<string, unknown> | null
}

export type ResolvableInstall = {
  status?: string | null
  installedEntityType?: string | null
  installedEntityId?: string | null
  metadata?: {
    agentId?: string
    agentIds?: string[]
  } | null
}

const ACTIVE_INSTALL = new Set(["active", "installed"])

function isPackBackedAgent(agent: ResolvableAgent): boolean {
  const config = agent.config ?? {}
  return Boolean(
    config.marketplaceAssetId ||
      config.pack_id ||
      config.packId ||
      config.marketplace_asset_id,
  )
}

function activeAgents(agents: ResolvableAgent[]): ResolvableAgent[] {
  const active = agents.filter((agent) => !agent.status || agent.status === "active")
  return active.length > 0 ? active : agents
}

/** Collect agent UUIDs from active marketplace installs (primary + multi-agent packs). */
export function collectInstalledAgentIds(installs: ResolvableInstall[]): string[] {
  const ids: string[] = []
  const seen = new Set<string>()

  for (const install of installs) {
    const status = (install.status || "active").toLowerCase()
    if (!ACTIVE_INSTALL.has(status)) continue

    const meta = install.metadata
    const candidates = [
      ...(Array.isArray(meta?.agentIds) ? meta.agentIds : []),
      ...(meta?.agentId ? [meta.agentId] : []),
      ...(install.installedEntityType === "agent" && install.installedEntityId
        ? [install.installedEntityId]
        : []),
    ]

    for (const id of candidates) {
      if (typeof id !== "string" || !id || seen.has(id)) continue
      seen.add(id)
      ids.push(id)
    }
  }

  return ids
}

/**
 * Pick a default agent for Assignments / similar single-agent flows.
 * Preference: explicit preferred → installed pack agent → pack-backed agent → sole/first active.
 */
export function resolveDefaultAgentId(options: {
  agents: ResolvableAgent[]
  preferredAgentId?: string | null
  installedAgentIds?: string[]
}): string | null {
  const pool = activeAgents(options.agents)
  if (pool.length === 0) return null

  const preferred = options.preferredAgentId
  if (preferred && pool.some((agent) => agent.id === preferred)) {
    return preferred
  }

  for (const id of options.installedAgentIds ?? []) {
    if (pool.some((agent) => agent.id === id)) return id
  }

  const packAgent = pool.find(isPackBackedAgent)
  if (packAgent) return packAgent.id

  return pool[0]?.id ?? null
}

/**
 * Prefill swarm coordinator + worker agents from pack installs / org agents.
 * Subtask slots reuse the parent when only one agent exists (objective still required).
 */
export function resolveSwarmAgentDefaults(options: {
  agents: ResolvableAgent[]
  installedAgentIds?: string[]
  maxSubtasks?: number
}): { parentAgentId: string; subtaskAgentIds: string[] } | null {
  const pool = activeAgents(options.agents)
  if (pool.length === 0) return null

  const parentAgentId = resolveDefaultAgentId(options)
  if (!parentAgentId) return null

  const maxSubtasks = options.maxSubtasks ?? 3
  const ordered: string[] = []
  const seen = new Set<string>()
  const push = (id: string | undefined) => {
    if (!id || seen.has(id) || !pool.some((agent) => agent.id === id)) return
    seen.add(id)
    ordered.push(id)
  }

  push(parentAgentId)
  for (const id of options.installedAgentIds ?? []) push(id)
  for (const agent of pool) push(agent.id)

  const workers = ordered.filter((id) => id !== parentAgentId).slice(0, maxSubtasks)
  const subtaskAgentIds = workers.length > 0 ? workers : [parentAgentId]

  return { parentAgentId, subtaskAgentIds }
}

/** Map org agents into builder council personas (real UUIDs for runtime agent_ids). */
export function resolveCouncilAgentDefaults(
  agents: ResolvableAgent[],
  installedAgentIds: string[] = [],
  limit = 3,
): Array<{ id: string; name: string; role: string; expertise: string; confidenceStyle: "analytical" }> {
  const defaults = resolveSwarmAgentDefaults({
    agents,
    installedAgentIds,
    maxSubtasks: Math.max(0, limit - 1),
  })
  if (!defaults) return []

  const ids = [defaults.parentAgentId, ...defaults.subtaskAgentIds].filter(
    (id, index, all) => all.indexOf(id) === index,
  )
  const byId = new Map(agents.map((agent) => [agent.id, agent]))

  return ids.slice(0, limit).map((id) => {
    const agent = byId.get(id)
    const name = agent?.name || "Agent"
    const role = agent?.role || "Contributor"
    return {
      id,
      name,
      role,
      expertise: role,
      confidenceStyle: "analytical" as const,
    }
  })
}
