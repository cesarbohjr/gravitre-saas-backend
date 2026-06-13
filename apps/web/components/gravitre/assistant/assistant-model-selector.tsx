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
  { id: "auto", label: "Auto (recommended)", group: "" },
  { id: "gpt-5.5", label: "GPT-5.5", description: "Most capable", group: "OpenAI" },
  { id: "gpt-5.4-mini", label: "GPT-5.4 Mini", description: "Fast & efficient", group: "OpenAI" },
  { id: "claude-sonnet-4-6", label: "Claude Sonnet 4.6", description: "Best for writing", group: "Anthropic" },
  { id: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5", description: "Fastest response", group: "Anthropic" },
  { id: "gemini-2.5-pro", label: "Gemini 2.5 Pro", description: "Multimodal", group: "Google" },
  { id: "gemini-2.5-flash", label: "Gemini 2.5 Flash", description: "Fast & cheap", group: "Google" },
] as const

const modes: { id: IntelligenceMode; label: string; icon: typeof Zap; color: string; placeholder: string }[] = [
  { id: "fast", label: "Fast", icon: Zap, color: "text-amber-500", placeholder: "Ask a quick question..." },
  { id: "standard", label: "Standard", icon: Gauge, color: "text-emerald-500", placeholder: "Ask anything about your AI team..." },
  { id: "reasoning", label: "Reasoning", icon: Brain, color: "text-violet-500", placeholder: "Describe a complex problem..." },
  { id: "agent", label: "Agent", icon: Bot, color: "text-sky-500", placeholder: "Describe a task to execute..." },
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
  const displayModel = modelOverride && modelOverride !== "auto"
    ? MODEL_OPTIONS.find((m) => m.id === modelOverride)?.label
    : null

  return (
    <div className="flex items-center gap-1">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-zinc-200 bg-white hover:bg-zinc-50 text-xs font-medium text-zinc-700">
            <Icon className={cn("h-3.5 w-3.5", current.color)} />
            <span>{current.label}</span>
            <ChevronDown className="h-3 w-3 text-zinc-400" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-48">
          {modes.map((m) => {
            const ModeIcon = m.icon
            return (
              <DropdownMenuItem key={m.id} onClick={() => onModeChange(m.id)} className={cn(mode === m.id && "bg-emerald-50")}>
                <ModeIcon className={cn("h-4 w-4 mr-2", m.color)} />
                <span className={cn("flex-1", mode === m.id && "text-emerald-700 font-medium")}>{m.label}</span>
                {mode === m.id && <Check className="h-3.5 w-3.5 text-emerald-600" />}
              </DropdownMenuItem>
            )
          })}
        </DropdownMenuContent>
      </DropdownMenu>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button className="p-1.5 rounded-lg border border-zinc-200 bg-white hover:bg-zinc-50 text-zinc-500" title="Choose model">
            <Settings2 className="h-3.5 w-3.5" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-56">
          <DropdownMenuLabel className="text-xs">Specific model</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {["", "OpenAI", "Anthropic", "Google"].map((group) => {
            const items = MODEL_OPTIONS.filter((m) => m.group === group)
            if (!items.length) return null
            return (
              <div key={group || "auto"}>
                {group && <DropdownMenuLabel className="text-[10px] text-zinc-400">{group}</DropdownMenuLabel>}
                {items.map((model) => (
                  <DropdownMenuItem
                    key={model.id}
                    onClick={() => {
                      onModelChange(model.id === "auto" ? null : model.id)
                      if (model.id !== "auto") onModeChange(inferModeFromModel(model.id))
                    }}
                  >
                    <span className="flex-1">{model.label}</span>
                    {(modelOverride === model.id || (!modelOverride && model.id === "auto")) && (
                      <Check className="h-3.5 w-3.5 text-emerald-600" />
                    )}
                  </DropdownMenuItem>
                ))}
              </div>
            )
          })}
        </DropdownMenuContent>
      </DropdownMenu>

      {displayModel && (
        <span className="hidden sm:inline text-[10px] text-zinc-400 truncate max-w-[80px]">[{displayModel}]</span>
      )}
    </div>
  )
}

export { modes as intelligenceModes }
