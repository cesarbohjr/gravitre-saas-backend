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
    accent: "text-emerald-600 dark:text-emerald-300",
    ring: "border-emerald-500/30 bg-emerald-500/10 ring-emerald-500/20",
  },
]

export const AI_EXAMPLE_PROMPTS: Array<{ text: string; hint: AiEngine }> = [
  {
    text: "Search Google Drive for the quarterly report and summarize the first page",
    hint: "chat",
  },
  { text: "Search HubSpot for high-intent leads and draft a follow-up in Slack for approval", hint: "chat" },
  { text: "Find failed workflow runs from the last 24 hours", hint: "chat" },
  { text: "Summarize our pipeline health and flag stale deals", hint: "chat" },
  { text: "Create a task in Asana for Sarah to review the landing page by Friday", hint: "chat" },
]

/** Prefill for composer “File lookup” — names Drive explicitly so connector routing can map search_files. */
export const CONNECTED_FILE_LOOKUP_TEMPLATE =
  "Search Google Drive for "

export function getModeMeta(id: ModeId): ModeMeta {
  return AI_MODES.find((mode) => mode.id === id) ?? AI_MODES[0]
}
