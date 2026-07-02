"use client"

import { cn } from "@/lib/utils"

const MODE_LABELS: Record<string, string> = {
  answer: "Answering",
  clarify: "Clarifying",
  confirm: "Awaiting approval",
  guide: "Planning",
  recommend: "Analyzing",
  execute: "Executing",
  simulate: "Simulating",
  research: "Retrieving",
  escalate: "Escalating",
  summarize: "Summarizing",
}

export function DialogueModeChip({
  mode,
  toolActivity,
}: {
  mode?: string | null
  toolActivity?: string | null
}) {
  const resolved =
    toolActivity ??
    (mode ? MODE_LABELS[mode] ?? mode.replace(/_/g, " ") : null)
  if (!resolved) return null

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-medium",
        "border-emerald-200 bg-emerald-50 text-emerald-700",
        "dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300",
      )}
    >
      {resolved}
    </span>
  )
}

export function mapToolNameToModeLabel(toolName?: string | null): string | null {
  if (!toolName) return null
  const normalized = toolName.toLowerCase()
  if (normalized.includes("knowledge") || normalized.includes("search")) return "Retrieving"
  if (normalized.includes("connector")) return "Checking connectors"
  if (normalized.includes("simulation") || normalized.includes("simulate")) return "Simulating"
  if (normalized.includes("approval")) return "Awaiting approval"
  return "Analyzing"
}
