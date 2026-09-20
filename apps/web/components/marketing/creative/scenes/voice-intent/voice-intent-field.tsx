"use client"

import { useEffect, useRef, useState } from "react"
import { useInView, useReducedMotion } from "framer-motion"
import { NucleoSuccess, NucleoVoice } from "@/components/icons/nucleo/semantic"
import { cn } from "@/lib/utils"
import { GravitreEvidenceMark } from "../../primitives/evidence-mark"
import { withCreativeScene } from "../../fallbacks/with-creative-scene"
import {
  ILLUSTRATIVE_CONTEXT,
  PHASE_CAPTION,
  STRUCTURE_CHIPS,
  VOICE_STAGES,
  VOICE_TURN_PATH_ID,
  activeStageIds,
  nextPhase,
  parseVoiceStateParam,
  showResponse,
  showStructure,
  showWaveform,
  type VoicePhase,
} from "./storyboard"

const WAVE_HEIGHTS = [10, 22, 16, 28, 14, 24, 18, 26, 12, 20, 15, 23]

function ReducedModel() {
  return (
    <div className="space-y-3 text-sm text-[color:var(--g-text-secondary)]">
      <p className="font-medium">Context</p>
      <p>{ILLUSTRATIVE_CONTEXT}</p>
      <p className="font-medium">Path</p>
      <p>{VOICE_STAGES.map((s) => s.label).join(" → ")}</p>
      <GravitreEvidenceMark label="No listening orb" />
      <GravitreEvidenceMark label="Same brain as chat" />
      <p className="text-[11px] text-[color:var(--g-text-muted)]">Not proven duplex parity.</p>
    </div>
  )
}

function WaveformBars({ active }: { active: boolean }) {
  return (
    <svg
      viewBox="0 0 200 40"
      className="pointer-events-none mx-auto h-10 w-56"
      aria-hidden
      data-testid="voice-waveform"
    >
      {WAVE_HEIGHTS.map((h, i) => {
        const x = 8 + i * 15
        const y = 20 - h / 2
        return (
          <rect
            key={i}
            x={x}
            y={active ? y : 18}
            width="8"
            height={active ? h : 4}
            rx="2"
            fill={active ? "#16a374" : "#c8cdd4"}
            opacity={active ? 0.85 : 0.45}
          />
        )
      })}
    </svg>
  )
}

function VoiceIntentFieldImpl({ className }: { className?: string }) {
  const reducePreference = useReducedMotion()
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  const reduced = mounted && !!reducePreference

  const rootRef = useRef<HTMLDivElement>(null)
  const inView = useInView(rootRef, { amount: 0.25, once: false })
  const [hidden, setHidden] = useState(false)
  const [frozenPhase, setFrozenPhase] = useState<VoicePhase | null>(null)
  const [phase, setPhase] = useState<VoicePhase>("quiet")

  useEffect(() => {
    const onVis = () => setHidden(document.hidden)
    onVis()
    document.addEventListener("visibilitychange", onVis)
    return () => document.removeEventListener("visibilitychange", onVis)
  }, [])

  useEffect(() => {
    if (typeof window === "undefined") return
    const frozen = parseVoiceStateParam(new URLSearchParams(window.location.search).get("voiceState"), {
      hostname: window.location.hostname,
    })
    setFrozenPhase(frozen)
    if (frozen) setPhase(frozen)
  }, [])

  useEffect(() => {
    if (frozenPhase || reduced || !inView || hidden) return
    const t = window.setTimeout(() => setPhase((p) => nextPhase(p)), phase === "action" ? 1500 : 1100)
    return () => window.clearTimeout(t)
  }, [phase, reduced, inView, hidden, frozenPhase])

  const lit = new Set(activeStageIds(phase))
  const wave = showWaveform(phase)
  const structure = showStructure(phase)
  const response = showResponse(phase)

  return (
    <div
      ref={rootRef}
      className={cn("mx-auto w-full max-w-3xl", className)}
      data-testid="voice-intent-field"
      data-creative-phase={phase}
      data-creative-frozen={frozenPhase ? "1" : "0"}
      data-voice-path-id={
        ["action", "response", "honest"].includes(phase) ? VOICE_TURN_PATH_ID : undefined
      }
    >
      {reduced ? (
        <div className="rounded-2xl border border-divide bg-white p-5" data-testid="voice-reduced">
          <ReducedModel />
        </div>
      ) : (
        <div className="rounded-2xl border border-divide bg-white p-4 md:p-6" data-testid="voice-desktop">
          <p className="text-center text-sm text-[color:var(--g-text-secondary)]">{ILLUSTRATIVE_CONTEXT}</p>

          <div className="mt-4 flex justify-center">
            <NucleoVoice
              className={cn("h-4 w-4", wave ? "text-brand" : "text-[color:var(--g-text-muted)]")}
              aria-hidden
            />
          </div>
          <WaveformBars active={wave && phase !== "quiet"} />

          {structure ? (
            <div className="mt-3 flex flex-wrap items-center justify-center gap-2" data-testid="voice-structure">
              {STRUCTURE_CHIPS.map((chip) => (
                <span
                  key={chip}
                  className="rounded-full border border-divide bg-slate-50 px-2.5 py-1 text-[11px] font-medium text-[color:var(--g-text-secondary)]"
                >
                  {chip}
                </span>
              ))}
            </div>
          ) : null}

          <div className="mt-5 flex flex-wrap items-center justify-center gap-2 md:gap-3">
            {VOICE_STAGES.map((stage, i) => {
              const on = lit.has(stage.id)
              return (
                <div key={stage.id} className="flex items-center gap-2 md:gap-3">
                  <div
                    className={cn(
                      "min-w-[4.25rem] rounded-xl border px-2.5 py-2 text-center",
                      on && "border-[color:var(--color-brand,#16a374)]",
                      !on && "border-divide opacity-60",
                    )}
                    data-testid={`voice-stage-${stage.id}`}
                    data-lit={on ? "1" : "0"}
                  >
                    <p
                      className={cn(
                        "text-[11px] font-semibold",
                        on ? "text-[color:var(--g-text-secondary)]" : "text-[color:var(--g-text-muted)]",
                      )}
                    >
                      {stage.label}
                    </p>
                  </div>
                  {i < VOICE_STAGES.length - 1 ? (
                    <span className="hidden text-[color:var(--g-text-muted)] sm:inline" aria-hidden>
                      →
                    </span>
                  ) : null}
                </div>
              )
            })}
          </div>

          {response ? (
            <div className="mt-4 flex flex-col items-center gap-1" data-testid="voice-response">
              <GravitreEvidenceMark label="Response in same turn" />
              <GravitreEvidenceMark label="Governed path — not a free agent" />
            </div>
          ) : null}
        </div>
      )}

      <p className="mt-3 text-center text-sm font-medium text-[color:var(--g-text-secondary)]" aria-live="polite">
        {reduced ? "Illustrative voice intent model." : PHASE_CAPTION[phase]}
      </p>
      <p className="mt-2 flex items-center justify-center gap-1 text-center text-[11px] text-[color:var(--g-text-muted)]">
        <NucleoSuccess className="h-3 w-3" aria-hidden />
        Illustrative voice path — structure, intent, context, action, response. Not proven duplex parity.
      </p>
    </div>
  )
}

export const VoiceIntentField = withCreativeScene(VoiceIntentFieldImpl, "voice-intent")
