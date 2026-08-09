"use client"

/**
 * Design-review comp for the voice UI surfaces.
 *
 * Renders the real shipped components — VoiceSessionPresence, VoiceModeToggle,
 * and AgentVoiceAssignment — so the review judges production code, not a mock.
 * State is driven by local fixtures because the four presence states cannot all
 * coexist in one live session. (Composer speech-to-text-only control is gone.)
 *
 * Capture-only: the parent /e2e/shots layout 404s this in production.
 */

import { useState } from "react"

import { AgentVoiceAssignment } from "@/components/gravitre/agent-voice-assignment"
import { VoiceModeToggle } from "@/components/gravitre/assistant/voice-mode-toggle"
import {
  VoiceSessionPresence,
  type VoicePresenceState,
} from "@/components/gravitre/assistant/voice-session-presence"
import type { AgentVoiceProfile } from "@/types/api"

function Panel({
  title,
  note,
  children,
}: {
  title: string
  note?: string
  children: React.ReactNode
}) {
  return (
    <section className="flex flex-col gap-3">
      <header className="flex flex-col gap-0.5">
        <h2 className="text-sm font-semibold text-foreground">{title}</h2>
        {note ? <p className="text-xs text-muted-foreground">{note}</p> : null}
      </header>
      {children}
    </section>
  )
}

const PRESENCE: { state: VoicePresenceState; label: string; billing?: boolean; detail?: string }[] =
  [
    { state: "idle", label: "Idle — voice open, no motion" },
    { state: "listening", label: "Listening — mic open", detail: "Speak when ready" },
    { state: "speaking", label: "Speaking — agent talking" },
    {
      state: "error",
      label: "Billing — credits needed",
      billing: true,
      detail: "Add credits to resume spoken replies",
    },
    { state: "error", label: "Fault — device or transport" },
  ]

export default function VoiceStatesShot() {
  // voice_id must match a fixture voice: card selection compares on voice_id, so
  // seeding only voice_key would render every card unselected.
  const [profile, setProfile] = useState<AgentVoiceProfile>({
    voice_source: "preset_library",
    voice_id: "shot-voice-atlas",
    voice_key: "atlas",
    tts_model: "eleven_turbo_v2_5",
    turn_sensitivity: "normal",
  })

  return (
    <main className="min-h-screen bg-background px-8 py-10">
      <div className="mx-auto flex max-w-5xl flex-col gap-10">
        <header className="flex flex-col gap-1">
          <h1 className="text-lg font-semibold tracking-tight text-foreground">
            Voice UI — design review
          </h1>
          <p className="text-sm text-muted-foreground">
            Real components. Presentation-only pass; entitlements, voice routes and
            voice_profile are untouched.
          </p>
        </header>

        <Panel
          title="Session presence"
          note="Motion budget is three states; idle is deliberately still so an open session never animates in an operator's periphery."
        >
          <div className="flex flex-col gap-2.5">
            {PRESENCE.map((p) => (
              <div key={p.label} className="flex items-center gap-4">
                <span className="w-56 shrink-0 text-xs text-muted-foreground">{p.label}</span>
                <VoiceSessionPresence
                  state={p.state}
                  billing={p.billing}
                  detail={p.detail}
                  className="w-72"
                />
              </div>
            ))}
          </div>
        </Panel>

        <Panel
          title="Modality toggle"
          note="Gated and live variants share one height so swapping never reflows the composer row."
        >
          <div className="flex flex-wrap items-center gap-6">
            <div className="flex items-center gap-3">
              <span className="text-xs text-muted-foreground">Text</span>
              <VoiceModeToggle mode="text" onChange={() => {}} voiceEntitled />
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-muted-foreground">Voice</span>
              <VoiceModeToggle mode="voice" onChange={() => {}} voiceEntitled />
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-muted-foreground">Not entitled</span>
              <VoiceModeToggle mode="text" onChange={() => {}} voiceEntitled={false} />
            </div>
          </div>
        </Panel>

        <Panel
          title="Agent voice assignment"
          note="Preset and custom are equal-weight paths. Voice identity reads as a name and source, not a raw voice_id."
        >
          <div className="rounded-xl border border-border/70 bg-card p-5">
            <AgentVoiceAssignment
              value={profile}
              onChange={setProfile}
              department="operations"
            />
          </div>
        </Panel>
      </div>
    </main>
  )
}
