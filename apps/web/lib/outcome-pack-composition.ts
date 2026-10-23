export type PackComposition = {
  agents: number; plays: number; knowledge: number; metrics: number; dashboards: number
  actions: string[]; skillPackages: string[]; approvalPlays: string[]
}
const rows = (value: unknown): Record<string, unknown>[] => Array.isArray(value)
  ? value.filter((row): row is Record<string, unknown> => row !== null && typeof row === "object" && !Array.isArray(row)) : []
const object = (value: unknown): Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {}
export function outcomePackComposition(config: Record<string, unknown> | undefined): PackComposition | null {
  if (!config || config.marketplace_version !== "3.0") return null
  const plays = rows(config.plays)
  const profiles = rows(config.runtime_profiles)
  return {
    agents: rows(config.agents).length, plays: plays.length, knowledge: rows(config.knowledge).length,
    metrics: rows(object(config.dataset).metrics).length, dashboards: Object.keys(object(config.dashboard)).length ? 1 : 0,
    actions: [...new Set(profiles.flatMap(profile => Array.isArray(profile.actions) ? profile.actions.filter((a): a is string => typeof a === "string") : []))].sort(),
    skillPackages: [...new Set(Object.values(object(config.skill_bindings)).filter((a): a is string => typeof a === "string" && Boolean(a.trim())))].sort(),
    approvalPlays: plays.filter(play => rows(play.approvals).length > 0 || rows(play.workflow_steps).some(step => step.type === "approval")).map(play => String(play.name ?? play.key ?? "Play")),
  }
}
