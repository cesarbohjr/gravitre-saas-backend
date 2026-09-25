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

function SettingRow({
  title,
  description,
  children,
  id,
}: {
  title: string
  description: string
  children: React.ReactNode
  id: string
}) {
  return (
    <div className="grid gap-4 py-6 first:pt-0 last:pb-0 lg:grid-cols-[minmax(200px,260px)_1fr] lg:gap-10">
      <div>
        <h3 id={id} className="text-sm font-semibold text-foreground">
          {title}
        </h3>
        <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">{description}</p>
      </div>
      <div className="min-w-0">{children}</div>
    </div>
  )
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
    <section
      aria-label="Personality"
      className={cn("divide-y divide-[color:var(--g-border-subtle)]", className)}
    >
      <SettingRow
        id="personality-voice"
        title="Spoken voice"
        description="How this agent sounds in voice conversations. Listen before you choose."
      >
        {showVoiceConfigure ? (
          <AgentVoiceAssignment
            value={voiceProfile}
            onChange={onVoiceProfileChange}
            department={department}
          />
        ) : (
          <p className="text-[13px] text-muted-foreground">
            Voice assignment requires a full or manager seat. Lite seats can use voice on agents
            already assigned to their department.
          </p>
        )}
      </SettingRow>

      <SettingRow
        id="personality-style"
        title="Response style"
        description="Tone and length of this agent's written replies in chat."
      >
        <div
          role="radiogroup"
          aria-labelledby="personality-style"
          className="grid gap-2 sm:grid-cols-2"
        >
          {AGENT_RESPONSE_STYLE_OPTIONS.map((option) => {
            const selected = option.key === selectedStyle
            return (
              <button
                key={option.key}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => onResponseStyleChange(option.key)}
                className={cn(
                  "flex items-start gap-3 rounded-[var(--np-radius-md)] border px-3 py-2.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  selected
                    ? "border-foreground bg-[color:var(--g-surface-1)]"
                    : "border-[color:var(--g-border-default)] hover:border-[color:var(--g-border-strong)] hover:bg-[color:var(--g-surface-1)]",
                )}
              >
                <span
                  aria-hidden
                  className={cn(
                    "mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full border",
                    selected
                      ? "border-foreground bg-foreground text-background"
                      : "border-[color:var(--g-border-strong)]",
                  )}
                >
                  {selected ? <Check className="size-2.5" strokeWidth={3} /> : null}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-[13px] font-medium text-foreground">
                    {option.label}
                  </span>
                  <span className="mt-0.5 block text-xs text-muted-foreground">
                    {[option.tone, option.verbosity].filter(Boolean).join(" · ")}
                  </span>
                </span>
              </button>
            )
          })}
        </div>
      </SettingRow>
    </section>
  )
}
