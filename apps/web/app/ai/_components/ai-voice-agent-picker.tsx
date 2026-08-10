"use client"

/**
 * Session voice-agent picker for main `/ai`.
 *
 * Replaces the retired Layout panels control. Operators pick which org agent
 * supplies spoken voice (and the transcript label). "Default" keeps the chat
 * persona / department session style without binding TTS to a specific agent.
 */

import { AudioLines, Check, ChevronDown } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type { Agent } from "@/types/api"
import { voiceProfileIsConfigured } from "@/lib/voice-configure-gate"

export const AI_VOICE_AGENT_DEFAULT = "default"

type AiVoiceAgentPickerProps = {
  agents: Agent[]
  value: string
  onChange: (agentId: string) => void
  disabled?: boolean
  loading?: boolean
  className?: string
}

export function AiVoiceAgentPicker({
  agents,
  value,
  onChange,
  disabled,
  loading,
  className,
}: AiVoiceAgentPickerProps) {
  const active = agents.filter((agent) => !agent.status || agent.status === "active")
  const selected = active.find((agent) => agent.id === value) ?? null
  const label = selected?.name ?? "Default voice"

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled || loading}
          className={cn("h-8 max-w-[min(100%,16rem)] gap-1.5 text-xs", className)}
          aria-label={`Voice agent: ${label}`}
        >
          <AudioLines className="h-3.5 w-3.5 shrink-0" aria-hidden />
          <span className="truncate">{loading ? "Loading agents…" : label}</span>
          <ChevronDown className="h-3 w-3 shrink-0 opacity-60" aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="z-[70] w-64">
        <DropdownMenuLabel className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          AI voice agent
        </DropdownMenuLabel>
        <DropdownMenuItem
          className="text-xs"
          onClick={() => onChange(AI_VOICE_AGENT_DEFAULT)}
        >
          <span className="flex min-w-0 flex-1 flex-col">
            <span className="truncate font-medium">Default voice</span>
            <span className="truncate text-[10px] text-muted-foreground">
              Session style · org default voice
            </span>
          </span>
          {value === AI_VOICE_AGENT_DEFAULT || !selected ? (
            <Check className="ml-2 h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />
          ) : null}
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        {active.length === 0 ? (
          <p className="px-2 py-1.5 text-[11px] text-muted-foreground">
            No agents yet. Admins can create voice agents under Agents.
          </p>
        ) : (
          active.map((agent) => {
            const hasVoice = voiceProfileIsConfigured(agent.voiceProfile)
            const isSelected = selected?.id === agent.id
            return (
              <DropdownMenuItem
                key={agent.id}
                className="text-xs"
                onClick={() => onChange(agent.id)}
              >
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate font-medium">{agent.name}</span>
                  <span className="truncate text-[10px] text-muted-foreground">
                    {agent.department || agent.role || "Agent"}
                    {hasVoice ? " · voice ready" : " · text · default voice"}
                  </span>
                </span>
                {isSelected ? (
                  <Check className="ml-2 h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />
                ) : null}
              </DropdownMenuItem>
            )
          })
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
