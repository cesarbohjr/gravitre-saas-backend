import type { Icon as PhosphorIcon } from "@phosphor-icons/react"
import { Sparkle as Sparkles } from "@phosphor-icons/react"
import type { AiEngine } from "@/lib/ai-surface-handoff"
export type ModeId = "auto" | AiEngine

export type ModeMeta = {
  id: ModeId
  label: string
  badge: string
  icon: PhosphorIcon
  blurb: string
  accent: string
  ring: string
}

export const AI_MODES: ModeMeta[] = [
  {
    id: "auto",
    label: "Unified",
    badge: "Answer · Search · Execute",
    icon: Sparkles,
    blurb: "One conversation — Gravitre answers, searches your stack, and runs connector actions with approval where needed.",
    accent: "text-foreground",
    ring: "border-foreground/30 bg-foreground/5 ring-foreground/15",
  },
<<<<<<< HEAD
  {
    id: "execute",
    label: "Execute",
    badge: "Execute",
    icon: RocketLaunch,
    blurb: "Delegate tracked work — tasks, execution plans, and async jobs.",
    accent: "text-primary",
    ring: "border-primary/40 bg-primary/5 ring-primary/20",
  },
  {
    id: "chat",
    label: "Chat",
    badge: "Chat",
    icon: ChatCircle,
    blurb: "Ask questions, brainstorm, and get platform help in a thread.",
    accent: "text-primary",
    ring: "border-primary/40 bg-primary/5 ring-primary/20",
  },
  {
    id: "find",
    label: "Search",
    badge: "Search",
    icon: MagnifyingGlass,
    blurb: "Locate a workflow, run, agent, connector, or document.",
    accent: "text-primary",
    ring: "border-primary/40 bg-primary/5 ring-primary/20",
  },
=======
>>>>>>> origin/main
]

export const AI_EXAMPLE_PROMPTS: Array<{ text: string; hint: AiEngine }> = [
  { text: "Search HubSpot for high-intent leads and draft a follow-up in Slack for approval", hint: "chat" },
  { text: "Find failed workflow runs from the last 24 hours", hint: "chat" },
  { text: "Summarize our pipeline health and flag stale deals", hint: "chat" },
  { text: "Create a task in Asana for Sarah to review the landing page by Friday", hint: "chat" },
]

export function getModeMeta(id: ModeId): ModeMeta {
  return AI_MODES.find((mode) => mode.id === id) ?? AI_MODES[0]
}
