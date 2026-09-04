"use client"

/**
 * Design-review comp for the voice UI surfaces.
 *
 * Renders the real shipped waveform + orb components with fixtured speaker
 * state. Text|Voice toggle and Speak mic are gone — the in-input waveform is
 * the control. Capture-only: the parent /e2e/shots layout 404s this in production.
 */

import { useState } from "react"

import { AgentVoiceAssignment } from "@/components/gravitre/agent-voice-assignment"
import {
  GravitreWave,
  VoiceOrbTakeover,
  type VoiceSpeaker,
} from "@/components/gravitre/assistant/voice-presentation"
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

function InputPill({
  speaker,
  active,
  label,
}: {
  speaker: VoiceSpeaker
  active: boolean
  label?: string
}) {
  return (
    <div
      className="flex h-11 w-full max-w-xl items-center gap-2 rounded-full border border-border/70 bg-white px-3 dark:bg-[#262626]"
      data-shot={active ? `wave-${speaker}` : "wave-idle"}
    >
      <GravitreWave speaker={speaker} active={active} compact />
      <span className="flex-1 text-xs text-muted-foreground">Ask, delegate, or search…</span>
      {label ? (
        <span
          className={
            speaker === "user" && active
              ? "text-xs font-medium text-[#16a374]"
              : "text-xs font-medium text-[#3f5b52] dark:text-[#e9e9e6]"
          }
        >
          {label}
        </span>
      ) : null}
    </div>
  )
}

export default function VoiceStatesShot() {
  const [profile, setProfile] = useState<AgentVoiceProfile>({
    voice_source: "preset_library",
    voice_id: "shot-voice-atlas",
    voice_key: "atlas",
    tts_model: "eleven_turbo_v2_5",
    turn_sensitivity: "normal",
  })
  const [orb, setOrb] = useState<VoiceSpeaker | null>(null)

  return (
    <main className="min-h-screen bg-background px-8 py-10">
      <div className="mx-auto flex max-w-5xl flex-col gap-10">
        <header className="flex flex-col gap-1">
          <h1 className="text-lg font-semibold tracking-tight text-foreground">
            Voice UI — design review
          </h1>
          <p className="text-sm text-muted-foreground">
            In-input waveform (11a/11b) and orb voice view. No Text|Voice toggle.
          </p>
        </header>

        <Panel
          title="Composer input pill"
          note="Grey/still when idle; emerald + You while you speak; graphite + agent name while TTS plays."
        >
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-4">
              <span className="w-40 shrink-0 text-xs text-muted-foreground">Idle</span>
              <InputPill speaker="user" active={false} />
            </div>
            <div className="flex items-center gap-4">
              <span className="w-40 shrink-0 text-xs text-muted-foreground">You (11a)</span>
              <InputPill speaker="user" active label="You" />
            </div>
            <div className="flex items-center gap-4">
              <span className="w-40 shrink-0 text-xs text-muted-foreground">Gravitre (11b)</span>
              <InputPill speaker="agent" active label="Gravitre" />
            </div>
          </div>
        </Panel>

        <Panel
          title="Orb — voice view"
          note="Immersive voice-to-voice presentation with exit + mic controls."
        >
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => setOrb("user")}
              className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium hover:bg-muted/50"
            >
              Open orb — you speaking
            </button>
            <button
              type="button"
              onClick={() => setOrb("agent")}
              className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium hover:bg-muted/50"
            >
              Open orb — Gravitre speaking
            </button>
          </div>
          {orb ? (
            <VoiceOrbTakeover
              speaker={orb}
              agentLabel="Gravitre"
              onExitVoice={() => setOrb(null)}
              onMicToggle={() => setOrb((current) => (current === "user" ? "agent" : "user"))}
              micActive
            />
          ) : null}
        </Panel>

        <Panel title="Voice assignment" note="Unchanged configure surface.">
          <AgentVoiceAssignment value={profile} onChange={setProfile} className="max-w-xl" />
        </Panel>
      </div>
    </main>
  )
}
