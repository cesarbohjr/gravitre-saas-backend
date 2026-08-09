"use client"

/**
 * VOICE_PRESENTATION — the two presentation modes for one live voice session.
 *
 * Waveform and orb are peers, not a primary plus an escape hatch. The same
 * session drives both, and switching between them must never touch the audio or
 * the transcript. That constraint is what decides the architecture here: this
 * module owns *presentation only*, and the session lives above it, so expanding
 * or collapsing cannot restart a mic or drop a transcript — there is simply no
 * session state in here to lose.
 *
 * Two distinct axes, deliberately not conflated:
 *   presentation  waveform <-> orb   (stays in voice mode)
 *   modality      voice    <-> text  (leaves voice mode entirely)
 * The orb's centre tap moves the first axis; its "✕" and "Tap to switch to text"
 * move the second. Collapsing the orb by tapping it must not end the call.
 *
 * Amplitude: the handoff asks for real amplitude when available, keyframes as
 * fallback. No AnalyserNode exists in the pipeline yet, so these are keyframes
 * driven by real *discrete* state (who is speaking, from the session the caller
 * already tracks). No amplitude prop is exposed until there is a real signal to
 * feed it — a prop that silently receives nothing would be worse than its
 * absence, because it would read as wired.
 */

import { useEffect, useRef } from "react"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * Who currently holds the floor. This maps 1:1 onto the presence state the chat
 * surfaces already track (`listening` = mic open = the user; `speaking` = TTS
 * playing = the agent), so no new state detection is introduced.
 */
export type VoiceSpeaker = "user" | "agent"

/** Per-speaker motion and color, verbatim from the handoff. */
const WAVE_DURATION: Record<VoiceSpeaker, string> = {
  // The user's own voice reads as immediate; the agent's is calmer and slower so
  // the two are distinguishable without reading the label.
  user: "0.6s",
  agent: "1.1s",
}

/**
 * Component 1 — inline waveform.
 *
 * Seven 3px bars. The heights, per-bar keyframes and stagger live in globals.css
 * as `.gv-wave-bar` / `gv-wave1..7`; keeping them in CSS (rather than a JS
 * animation) is what lets `prefers-reduced-motion` freeze them with the bars
 * still at distinct resting heights, so a frozen waveform still reads as a
 * waveform instead of seven identical stubs.
 */
export function GravitreVoiceWaveform({
  speaker,
  compact = false,
  className,
}: {
  speaker: VoiceSpeaker
  /** Icon-scale rendering for the compact session strip. Same bars, same keyframes. */
  compact?: boolean
  className?: string
}) {
  return (
    <span
      aria-hidden
      className={cn(
        "flex items-center gap-[3px]",
        // Bars are `background-color: currentColor`, so speaker color is set here
        // once rather than on each of the seven.
        speaker === "user" ? "text-[#16a374]" : "text-[#3f5b52] dark:text-[#e9e9e6]",
        // Scaled, not re-declared at a second set of sizes: one waveform
        // implementation serves both the composer and the compact strip.
        compact && "scale-[0.55]",
        className,
      )}
      style={{ ["--gv-wave-duration" as string]: WAVE_DURATION[speaker] }}
    >
      {Array.from({ length: 7 }, (_, i) => (
        <span key={i} className="gv-wave-bar" />
      ))}
    </span>
  )
}

/**
 * Component 2 — full-screen orb takeover.
 *
 * Hit areas are siblings in a stacking order, never nested: the centre tap layer
 * is a button covering the surface, with "✕" and the bottom control painted above
 * it. Nesting them would be invalid HTML and, worse, a tap on "✕" would also
 * fire the collapse handler underneath — exiting voice mode AND collapsing.
 */
export function VoiceOrbTakeover({
  speaker,
  agentLabel = "Gravitre",
  onCollapse,
  onExitVoice,
}: {
  speaker: VoiceSpeaker
  agentLabel?: string
  /** Return to the inline waveform. Stays in voice mode. */
  onCollapse: () => void
  /** Leave voice mode entirely, back to typed text. */
  onExitVoice: () => void
}) {
  // Escape collapses rather than exits. Escape conventionally dismisses the
  // overlay, and the overlay here is a *presentation*, so dismissing it must not
  // silently end a live call — the destructive action stays explicit ("✕").
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation()
        onCollapse()
      }
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [onCollapse])

  // `aria-modal="true"` asserts that everything behind this overlay is
  // unreachable, so focus has to actually move inside it — otherwise a keyboard or
  // screen-reader user stays parked on the composer underneath, tabbing through
  // controls the overlay claims are gone. Focus lands on collapse (the least
  // destructive control) and is restored to the opener on unmount.
  const collapseRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null
    collapseRef.current?.focus()
    return () => opener?.focus?.()
  }, [])

  const isUser = speaker === "user"
  const label = isUser ? "You're speaking…" : `${agentLabel} is speaking…`

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Voice session — ${label}`}
      data-voice-orb=""
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#111110] sm:p-6"
    >
      {/* Desktop caps the surface at the handoff's ~900x560; mobile is full-bleed. */}
      <div className="relative flex h-full w-full max-w-full flex-col items-center justify-center overflow-hidden sm:h-[560px] sm:w-[900px] sm:rounded-2xl">
        {/*
          Centre tap layer — collapse back to the waveform. Rendered first so the
          explicit controls below sit above it in paint order, and given a label
          because a full-surface button is otherwise unannounced.
        */}
        <button
          ref={collapseRef}
          type="button"
          onClick={onCollapse}
          aria-label="Return to inline waveform, stay in voice mode"
          className="absolute inset-0 z-0 cursor-default focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-white/40"
        />

        <span className="pointer-events-none absolute left-5 top-5 z-10 flex flex-col gap-1 text-[13px] text-[rgba(255,255,255,0.5)]">
          {label}
          {/*
            The centre-tap gesture is invisible, and the bottom control reads
            "Tap to switch to text" — so without this hint the most natural
            reading is that tapping anywhere switches to text, when it actually
            minimises. Naming the gesture is what separates the two outcomes.
          */}
          <span className="text-[11px] text-[rgba(255,255,255,0.35)]">
            Tap anywhere to minimise
          </span>
        </span>

        <button
          type="button"
          onClick={onExitVoice}
          aria-label="Exit voice mode"
          className="absolute right-4 top-4 z-10 flex h-9 w-9 items-center justify-center rounded-full text-[rgba(255,255,255,0.6)] transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50"
        >
          <X className="h-5 w-5" aria-hidden />
        </button>

        {/* The orb itself is decorative; the state it conveys is announced by the
            label above, so it carries no semantics of its own. */}
        <div
          aria-hidden
          data-voice-orb-circle=""
          className={cn(
            "pointer-events-none relative z-0 h-[220px] w-[220px] rounded-full sm:h-[280px] sm:w-[280px]",
            isUser ? "gv-orb-user" : "gv-orb-agent",
          )}
          style={{
            backgroundImage: isUser
              ? "radial-gradient(circle at 35% 30%, #34d399, #16a374 55%, #0f5132 100%)"
              : "radial-gradient(circle at 35% 30%, #f2f2f0, #b9b9b6 55%, #6b6b68 100%)",
          }}
        />

        {/*
          Exits voice mode entirely — the same action as "✕", not a second way to
          collapse. Kept as its own hit area well clear of the centre tap layer so
          the two outcomes cannot be confused by a near-miss tap.
        */}
        <button
          type="button"
          onClick={onExitVoice}
          className="absolute bottom-8 left-1/2 z-10 -translate-x-1/2 rounded-full px-4 py-2 text-[14px] text-[rgba(255,255,255,0.6)] transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50"
        >
          Tap to switch to text
        </button>
      </div>
    </div>
  )
}
