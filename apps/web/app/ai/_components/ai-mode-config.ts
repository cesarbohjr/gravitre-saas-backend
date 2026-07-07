import type { Icon as PhosphorIcon } from "@phosphor-icons/react"
import {
  Sparkle as Sparkles,
  RocketLaunch,
  ChatCircle,
  MagnifyingGlass,
} from "@phosphor-icons/react"
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
    label: "Auto",
    badge: "Routes intent",
    icon: Sparkles,
    blurb: "Describe what you need — Gravitre picks the right engine.",
    accent: "text-foreground",
    ring: "border-foreground/30 bg-foreground/5 ring-foreground/15",
  },
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
]

export const AI_EXAMPLE_PROMPTS: Array<{ text: string; hint: AiEngine }> = [
  { text: "Investigate why the nightly Salesforce sync failed and fix it", hint: "execute" },
  { text: "What changed in our workflow success rate this week?", hint: "chat" },
  { text: "Find failed runs from the last 24 hours", hint: "find" },
  { text: "Draft an onboarding workflow for new support agents", hint: "execute" },
]

export function getModeMeta(id: ModeId): ModeMeta {
  return AI_MODES.find((mode) => mode.id === id) ?? AI_MODES[0]
}
