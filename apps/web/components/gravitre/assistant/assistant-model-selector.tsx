"use client"

import { Check, ChevronDown, Settings2, Zap, Brain, Gauge, Bot } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

export type IntelligenceMode = "fast" | "standard" | "reasoning" | "agent"

export const MODEL_OPTIONS = [
  { id: "auto", label: "Auto (recommended)", shortLabel: "Auto", group: "featured" },
  { id: "gpt-6-astra", label: "GPT-6 Astra", shortLabel: "GPT-6", description: "Most capable", group: "featured" },
  {
    id: "claude-opus-5-5",
    label: "Claude Opus 5.5",
    shortLabel: "Claude Opus",
    description: "Best for writing and reasoning",
    group: "featured",
  },
  {
    id: "gemini-3.1-pro-preview",
    label: "Gemini 3.1 Pro",
    shortLabel: "Gemini Pro",
    description: "Multimodal, long context",
    group: "featured",
  },
  { id: "gpt-6.1-sol", label: "GPT-6.1 Sol", shortLabel: "GPT-6.1 Sol", description: "Balanced", group: "OpenAI" },
  { id: "gpt-6-luna", label: "GPT-6 Luna", shortLabel: "GPT-6 Luna", description: "Fast & cheap", group: "OpenAI" },
  { id: "claude-fable-5-1", label: "Claude Fable 5.1", shortLabel: "Fable", description: "Hardest long tasks", group: "Anthropic" },
  { id: "claude-sonnet-5-5", label: "Claude Sonnet 5.5", shortLabel: "Sonnet", description: "Balanced", group: "Anthropic" },
  { id: "claude-haiku-4-5", label: "Claude Haiku 4.5", shortLabel: "Haiku", description: "Fastest response", group: "Anthropic" },
  { id: "gemini-3.8-flash", label: "Gemini 3.8 Flash", shortLabel: "Gemini Flash", description: "Fast & capable", group: "Google" },
  { id: "gemini-3.1-flash-lite", label: "Gemini 3.1 Flash-Lite", shortLabel: "Flash-Lite", description: "Cheapest", group: "Google" },
] as const

const modes: {
  id: IntelligenceMode
  label: string
  description: string
  icon: typeof Zap
  color: string
  activeBg: string
  placeholder: string
}[] = [
  {
    id: "fast",
    label: "Fast",
    description: "Quick questions",
    icon: Zap,
    color: "text-amber-500",
    activeBg: "bg-amber-500/10 border-amber-500/30",
    placeholder: "Ask a quick question...",
  },
  {
    id: "standard",
    label: "Standard",
    description: "Balanced default",
    icon: Gauge,
    color: "text-[color:var(--g-brand)]",
    activeBg: "bg-[color:var(--g-brand-soft)] border-[color:var(--g-brand-border)]",
    placeholder: "Ask anything about your AI team...",
  },
  {
    id: "reasoning",
    label: "Reasoning",
    description: "Complex analysis",
    icon: Brain,
    color: "text-[color:var(--g-brand-active)]",
    activeBg: "bg-[color:var(--g-brand-surface)] border-[color:var(--g-brand-border)]",
    placeholder: "Describe a complex problem to analyze...",
  },
  {
    id: "agent",
    label: "Agent",
    description: "Execute tasks",
    icon: Bot,
    color: "text-[color:var(--g-signal)]",
    activeBg: "bg-[color:var(--g-signal)]/10 border-[color:var(--g-signal)]/30",
    placeholder: "Describe a task for the agent to execute...",
  },
]

export function getModeConfig(mode: IntelligenceMode) {
  return modes.find((m) => m.id === mode) || modes[1]
}

export function inferModeFromModel(model: string | null): IntelligenceMode {
  if (!model || model === "auto") return "standard"
  if (["gpt-5.4-mini", "claude-haiku-4-5-20251001", "gemini-2.5-flash"].includes(model)) return "fast"
  if (["gpt-5.5", "claude-sonnet-4-6", "gemini-2.5-pro"].includes(model)) return "reasoning"
  return "standard"
}

interface AssistantModelSelectorProps {
  mode: IntelligenceMode
  modelOverride: string | null
  onModeChange: (mode: IntelligenceMode) => void
  onModelChange: (model: string | null) => void
}

export function AssistantModelSelector({
  mode,
  modelOverride,
  onModeChange,
  onModelChange,
}: AssistantModelSelectorProps) {
  const current = getModeConfig(mode)
  const Icon = current.icon
  const activeModelId = modelOverride && modelOverride !== "auto" ? modelOverride : "auto"
  const activeModel = MODEL_OPTIONS.find((m) => m.id === activeModelId)
  const modelBadgeLabel = activeModel?.shortLabel ?? "Auto"

  const modelGroups: { key: string; label: string | null }[] = [
    { key: "featured", label: "Recommended" },
    { key: "OpenAI", label: "OpenAI" },
    { key: "Anthropic", label: "Anthropic" },
    { key: "Google", label: "Google" },
  ]

  return (
    <div className="flex shrink-0 items-center gap-1.5">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label={`Intelligence mode: ${current.label}`}
            className={cn(
              "flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-semibold transition-colors",
              current.activeBg,
              "text-foreground hover:opacity-90",
            )}
          >
            <Icon className={cn("h-3.5 w-3.5", current.color)} />
            <span>{current.label}</span>
            <ChevronDown className="h-3 w-3 text-muted-foreground" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-56">
          <DropdownMenuLabel className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Intelligence mode
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          {modes.map((m) => {
            const ModeIcon = m.icon
            const selected = mode === m.id
            return (
              <DropdownMenuItem
                key={m.id}
                onClick={() => onModeChange(m.id)}
                className={cn(
                  "flex flex-col items-stretch gap-0.5 py-2.5",
                  selected && "bg-[color:var(--g-brand-soft)]",
                )}
              >
                <div className="flex items-center gap-2">
                  <ModeIcon className={cn("h-4 w-4 shrink-0", m.color)} />
                  <span className={cn("flex-1 text-sm", selected && "font-semibold text-emerald-700 dark:text-emerald-300")}>
                    {m.label}
                  </span>
                  {selected && <Check className="h-3.5 w-3.5 shrink-0 text-emerald-600" />}
                </div>
                <span className="pl-6 text-[11px] leading-snug text-muted-foreground">{m.description}</span>
              </DropdownMenuItem>
            )
          })}
        </DropdownMenuContent>
      </DropdownMenu>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className="rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-1)] p-1.5 text-muted-foreground transition-colors hover:bg-[color:var(--g-surface-2)]"
            aria-label="Choose model"
            title="Choose model"
          >
            <Settings2 className="h-3.5 w-3.5" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-60">
          <DropdownMenuLabel className="text-xs">Model</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {modelGroups.map(({ key, label }) => {
            const items = MODEL_OPTIONS.filter((m) => m.group === key)
            if (!items.length) return null
            return (
              <div key={key}>
                {label && (
                  <DropdownMenuLabel className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                    {label}
                  </DropdownMenuLabel>
                )}
                {items.map((model) => {
                  const selected =
                    (modelOverride === model.id) || (!modelOverride && model.id === "auto")
                  return (
                    <DropdownMenuItem
                      key={model.id}
                      onClick={() => {
                        onModelChange(model.id === "auto" ? null : model.id)
                        if (model.id !== "auto") onModeChange(inferModeFromModel(model.id))
                      }}
                      className="flex flex-col items-stretch gap-0.5 py-2"
                    >
                      <div className="flex items-center gap-2">
                        <span className="flex-1 text-sm">{model.label}</span>
                        {selected && <Check className="h-3.5 w-3.5 shrink-0 text-emerald-600" />}
                      </div>
                      {"description" in model && model.description ? (
                        <span className="text-[10px] text-muted-foreground">{model.description}</span>
                      ) : null}
                    </DropdownMenuItem>
                  )
                })}
              </div>
            )
          })}
        </DropdownMenuContent>
      </DropdownMenu>

      <span
        className="hidden rounded-[var(--np-radius-sm)] border border-divide bg-[color:var(--g-surface-1)] px-2 py-0.5 text-[10px] font-medium text-muted-foreground sm:inline"
        title={`Model: ${activeModel?.label ?? "Auto"}`}
      >
        {modelBadgeLabel}
      </span>
    </div>
  )
}

export { modes as intelligenceModes }
