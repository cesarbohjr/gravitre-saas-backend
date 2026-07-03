export type AiWorkSurfaceId = "gravitre-ai" | "workspace-chat" | "universal-search"

export type AiWorkSurface = {
  id: AiWorkSurfaceId
  href: string
  title: string
  badge: string
  summary: string
  whenToUse: string
  notThis: string
}

import { APP_ROUTES } from "@/lib/app-routes"

/** Shared copy for Gravitre AI, Workspace Chat, and Universal Search. */
export const AI_WORK_SURFACES: AiWorkSurface[] = [
  {
    id: "gravitre-ai",
    href: APP_ROUTES.gravitreAi,
    title: "Gravitre AI",
    badge: "Unified",
    summary: "One intelligent front door — execute tracked work, chat with tools, or find records across your org.",
    whenToUse: "When you want Gravitre to route your intent to the right engine automatically.",
    notThis: "Not three separate products — one unified AI workspace.",
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
