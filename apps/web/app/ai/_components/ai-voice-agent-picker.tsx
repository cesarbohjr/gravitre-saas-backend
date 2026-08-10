"use client"

/**
 * Session spoken-voice picker for main `/ai`.
 *
 * Distinct from ChatSessionControls (department / response style / speed).
 * This control only chooses which configured agent voice speaks replies —
 * it does not change writing style or transcript identity.
 *
 * Agents without a voiceProfile are omitted so the menu never looks like a
 * second agent roster of "text · default voice" placeholders.
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

function voiceLabel(agent: Agent): string {
  const profile = agent.voiceProfile
  const key = profile?.voice_key?.trim()
  if (key) {
    return key
      .replace(/[-_]+/g, " ")
      .replace(/\b\w/g, (ch) => ch.toUpperCase())
  }
  const descriptor = profile?.personality_attributes?.descriptor?.trim()
  if (descriptor) return descriptor
  return "Configured voice"
}

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
  const voiced = agents.filter(
    (agent) =>
      (!agent.status || agent.status === "active") && voiceProfileIsConfigured(agent.voiceProfile),
  )
  const selected = voiced.find((agent) => agent.id === value) ?? null
  const triggerLabel = selected
    ? `${voiceLabel(selected)} · ${selected.name}`
    : "Default spoken voice"

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled || loading}
          className={cn("h-8 max-w-[min(100%,16rem)] gap-1.5 text-xs", className)}
          aria-label={`Spoken voice: ${triggerLabel}`}
        >
          <AudioLines className="h-3.5 w-3.5 shrink-0" aria-hidden />
          <span className="truncate">{loading ? "Loading voices…" : triggerLabel}</span>
          <ChevronDown className="h-3 w-3 shrink-0 opacity-60" aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="z-[70] w-72">
        <DropdownMenuLabel className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          Spoken voice
        </DropdownMenuLabel>
        <p className="px-2 pb-1.5 text-[10px] leading-snug text-muted-foreground">
          How replies sound. Response style (next to this) still controls how they are written.
        </p>
        <DropdownMenuItem
          className="text-xs"
          onClick={() => onChange(AI_VOICE_AGENT_DEFAULT)}
        >
          <span className="flex min-w-0 flex-1 flex-col">
            <span className="truncate font-medium">Default spoken voice</span>
            <span className="truncate text-[10px] text-muted-foreground">
              Org default · not tied to an agent
            </span>
          </span>
          {value === AI_VOICE_AGENT_DEFAULT || !selected ? (
            <Check className="ml-2 h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />
          ) : null}
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        {voiced.length === 0 ? (
          <p className="px-2 py-1.5 text-[11px] text-muted-foreground">
            No agent voices configured yet. Admins assign an ElevenLabs voice on an agent under
            Agents — then it appears here for speaking.
          </p>
        ) : (
          voiced.map((agent) => {
            const isSelected = selected?.id === agent.id
            return (
              <DropdownMenuItem
                key={agent.id}
                className="text-xs"
                onClick={() => onChange(agent.id)}
              >
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate font-medium">{voiceLabel(agent)}</span>
                  <span className="truncate text-[10px] text-muted-foreground">
                    Use {agent.name}&apos;s voice
                    {agent.department ? ` · ${agent.department}` : ""}
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
