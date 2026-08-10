"use client"

/**
 * Personality block for agent create + profile edit.
 * Spoken voice (ElevenLabs via AgentVoiceAssignment) + response style (text persona).
 */

import { Check } from "lucide-react"
import { cn } from "@/lib/utils"
import { AgentVoiceAssignment } from "@/components/gravitre/agent-voice-assignment"
import {
  AGENT_RESPONSE_STYLE_OPTIONS,
  normalizeAgentResponseStyle,
  responseStyleLabel,
} from "@/lib/agent-response-style"
import type { AgentVoiceProfile } from "@/types/api"

type AgentPersonalitySectionProps = {
  voiceProfile: AgentVoiceProfile
  onVoiceProfileChange: (profile: AgentVoiceProfile) => void
  responseStyle: string
  onResponseStyleChange: (key: string) => void
  department?: string
  showVoiceConfigure?: boolean
  className?: string
}

export function AgentPersonalitySection({
  voiceProfile,
  onVoiceProfileChange,
  responseStyle,
  onResponseStyleChange,
  department,
  showVoiceConfigure = true,
  className,
}: AgentPersonalitySectionProps) {
  const selectedStyle = normalizeAgentResponseStyle(responseStyle)

  return (
    <section className={cn("space-y-5", className)}>
      <div>
        <h3 className="text-base font-semibold text-foreground">Personality</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Spoken voice is how the agent sounds. Response style is how it writes in text.
        </p>
      </div>

      <div className="space-y-2">
        <p className="text-sm font-medium text-foreground">Spoken voice</p>
        {showVoiceConfigure ? (
          <AgentVoiceAssignment
            value={voiceProfile}
            onChange={onVoiceProfileChange}
            department={department}
          />
        ) : (
          <p className="rounded-md border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
            Voice assignment requires a full or manager seat. Lite seats can use voice on agents
            already assigned to their department.
          </p>
        )}
      </div>

      <div className="space-y-2">
        <p className="text-sm font-medium text-foreground">Response style</p>
        <p className="text-xs text-muted-foreground">
          Controls tone and verbosity in text chat for this agent ({responseStyleLabel(selectedStyle)}
          ).
        </p>
        <div className="grid gap-2 sm:grid-cols-2">
          {AGENT_RESPONSE_STYLE_OPTIONS.map((option) => {
            const selected = option.key === selectedStyle
            return (
              <button
                key={option.key}
                type="button"
                onClick={() => onResponseStyleChange(option.key)}
                className={cn(
                  "flex items-start gap-2 rounded-lg border px-3 py-2.5 text-left transition-colors",
                  selected
                    ? "border-foreground/40 bg-card"
                    : "border-border bg-secondary/40 hover:border-foreground/20",
                )}
              >
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium text-foreground">{option.label}</span>
                  <span className="mt-0.5 block text-[11px] text-muted-foreground">
                    {[option.tone, option.verbosity].filter(Boolean).join(" · ")}
                  </span>
                </span>
                {selected ? (
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-foreground" aria-hidden />
                ) : null}
              </button>
            )
          })}
        </div>
      </div>
    </section>
  )
}
