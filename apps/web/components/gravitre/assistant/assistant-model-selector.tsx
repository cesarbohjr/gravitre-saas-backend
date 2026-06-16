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
  { id: "gpt-5.5", label: "GPT-5.5", shortLabel: "GPT-5.5", description: "Most capable", group: "featured" },
  {
    id: "claude-sonnet-4-6",
    label: "Claude Sonnet 4.6",
    shortLabel: "Claude Sonnet",
    description: "Best for writing",
    group: "featured",
  },
  {
    id: "gemini-2.5-pro",
    label: "Gemini 2.5 Pro",
    shortLabel: "Gemini Pro",
    description: "Multimodal",
    group: "featured",
  },
  { id: "gpt-5.4-mini", label: "GPT-5.4 Mini", shortLabel: "GPT-5.4 Mini", description: "Fast & efficient", group: "OpenAI" },
  { id: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5", shortLabel: "Haiku", description: "Fastest response", group: "Anthropic" },
  { id: "gemini-2.5-flash", label: "Gemini 2.5 Flash", shortLabel: "Gemini Flash", description: "Fast & cheap", group: "Google" },
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
    activeBg: "bg-amber-50 border-amber-200",
    placeholder: "Ask a quick question...",
  },
  {
    id: "standard",
    label: "Standard",
    description: "Balanced default",
    icon: Gauge,
    color: "text-emerald-500",
    activeBg: "bg-emerald-50 border-emerald-200",
    placeholder: "Ask anything about your AI team...",
  },
  {
    id: "reasoning",
    label: "Reasoning",
    description: "Complex analysis",
    icon: Brain,
    color: "text-violet-500",
    activeBg: "bg-violet-50 border-violet-200",
    placeholder: "Describe a complex problem to analyze...",
  },
  {
    id: "agent",
    label: "Agent",
    description: "Execute tasks",
    icon: Bot,
    color: "text-sky-500",
    activeBg: "bg-sky-50 border-sky-200",
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
              "text-zinc-800 hover:opacity-90",
            )}
          >
            <Icon className={cn("h-3.5 w-3.5", current.color)} />
            <span>{current.label}</span>
            <ChevronDown className="h-3 w-3 text-zinc-400" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-56">
          <DropdownMenuLabel className="text-[10px] uppercase tracking-wider text-zinc-400">
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
                className={cn("flex flex-col items-stretch gap-0.5 py-2.5", selected && "bg-emerald-50")}
              >
                <div className="flex items-center gap-2">
                  <ModeIcon className={cn("h-4 w-4 shrink-0", m.color)} />
                  <span className={cn("flex-1 text-sm", selected && "font-semibold text-emerald-800")}>
                    {m.label}
                  </span>
                  {selected && <Check className="h-3.5 w-3.5 shrink-0 text-emerald-600" />}
                </div>
                <span className="pl-6 text-[11px] leading-snug text-zinc-500">{m.description}</span>
              </DropdownMenuItem>
            )
          })}
        </DropdownMenuContent>
      </DropdownMenu>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className="rounded-lg border border-zinc-200 bg-white p-1.5 text-zinc-500 transition-colors hover:bg-zinc-50"
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
                  <DropdownMenuLabel className="text-[10px] font-medium uppercase tracking-wider text-zinc-400">
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
                        <span className="text-[10px] text-zinc-500">{model.description}</span>
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
        className="hidden rounded-full border border-zinc-200 bg-white px-2 py-0.5 text-[10px] font-medium text-zinc-500 sm:inline"
        title={`Model: ${activeModel?.label ?? "Auto"}`}
      >
        {modelBadgeLabel}
      </span>
    </div>
  )
}

export { modes as intelligenceModes }
