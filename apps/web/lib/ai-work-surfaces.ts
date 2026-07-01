export type AiWorkSurfaceId = "command-center" | "workspace-chat" | "universal-search"

export type AiWorkSurface = {
  id: AiWorkSurfaceId
  href: string
  title: string
  badge: string
  summary: string
  whenToUse: string
  notThis: string
}

/** Shared copy for Command Center, Workspace Chat, and Universal Search. */
export const AI_WORK_SURFACES: AiWorkSurface[] = [
  {
    id: "command-center",
    href: "/operator",
    title: "Command Center",
    badge: "Execute",
    summary: "Delegate work — create tasks, generate execution plans, run async jobs, and track approvals.",
    whenToUse: "When you want Gravitre to do something and follow it through to completion.",
    notThis: "Not a free-form chat thread.",
  },
  {
    id: "workspace-chat",
    href: "/assistant",
    title: "Workspace Chat",
    badge: "Chat",
    summary: "Multi-turn conversation with tools, daily briefings, and platform help.",
    whenToUse: "When you want to ask questions, brainstorm, or explore ideas in a saved thread.",
    notThis: "Not for delegating tracked operator tasks.",
  },
  {
    id: "universal-search",
    href: "/search",
    title: "Universal Search",
    badge: "Find",
    summary: "Find workflows, runs, agents, connectors, and documents across your org.",
    whenToUse: "When you know what you are looking for and need a link to the record.",
    notThis: "Not a chat — it returns search results, not conversational answers.",
  },
]

export function getAiWorkSurface(id: AiWorkSurfaceId): AiWorkSurface {
  const surface = AI_WORK_SURFACES.find((entry) => entry.id === id)
  if (!surface) {
    throw new Error(`Unknown AI work surface: ${id}`)
  }
  return surface
}
