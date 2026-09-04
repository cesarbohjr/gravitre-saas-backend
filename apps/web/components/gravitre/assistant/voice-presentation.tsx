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
 * Amplitude: real AnalyserNode levels when the duplex session supplies `levels`
 * (7 bins, 0–1). Keyframes remain the fallback when levels are omitted so idle /
 * unsupported paths still read as a waveform.
 */

import { useEffect, useRef } from "react"
import { Mic, MicOff, X } from "lucide-react"
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
  active = true,
  levels,
  className,
}: {
  speaker: VoiceSpeaker
  /** Icon-scale rendering for the compact session strip. Same bars, same keyframes. */
  compact?: boolean
  /**
   * When false, bars stay grey and still (composer idle affordance). Animation
   * and speaker color only apply while someone holds the floor.
   */
  active?: boolean
  /**
   * Real AnalyserNode bins (length 7, 0–1). When provided and active, bar heights
   * are driven by amplitude instead of CSS keyframes.
   */
  levels?: number[] | null
  className?: string
}) {
  const reactive = Boolean(active && levels && levels.length >= 7)
  return (
    <span
      aria-hidden
      data-voice-waveform={reactive ? "analyser" : "keyframe"}
      className={cn(
        "flex items-center gap-[3px]",
        // Bars are `background-color: currentColor`, so speaker color is set here
        // once rather than on each of the seven.
        !active
          ? "text-[#9a9a96] dark:text-[#6b6b68]"
          : speaker === "user"
            ? "text-[#16a374]"
            : "text-[#3f5b52] dark:text-[#e9e9e6]",
        // Animation is opt-in via this class — see globals.css `.gv-wave-active`.
        // Skip keyframes when AnalyserNode levels drive height.
        active && !reactive && "gv-wave-active",
        // Scaled, not re-declared at a second set of sizes: one waveform
        // implementation serves both the composer and the compact strip.
        compact && "scale-[0.55]",
        className,
      )}
      style={{ ["--gv-wave-duration" as string]: WAVE_DURATION[speaker] }}
    >
      {Array.from({ length: 7 }, (_, i) => {
        const level = reactive ? Math.max(0, Math.min(1, levels![i] ?? 0)) : null
        const minPx = compact ? 3 : 4
        const maxPx = compact ? 14 : 18
        const height =
          level == null ? undefined : `${Math.round(minPx + level * (maxPx - minPx))}px`
        return (
          <span
            key={i}
            className="gv-wave-bar"
            style={height ? { height, animation: "none" } : undefined}
          />
        )
      })}
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
  onExitVoice,
  onMicToggle,
  micActive = true,
  amplitude,
}: {
  speaker: VoiceSpeaker
  agentLabel?: string
  /** Leave voice mode entirely, back to typed text. */
  onExitVoice: () => void
  /** Toggle mic/listening while staying in voice mode. */
  onMicToggle?: () => void
  micActive?: boolean
  /** Optional AnalyserNode peak 0–1 — scales the orb when present. */
  amplitude?: number | null
}) {
  // Escape exits voice mode to avoid trapping users inside full-screen voice UI.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation()
        onExitVoice()
      }
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [onExitVoice])

  // `aria-modal="true"` asserts that everything behind this overlay is unreachable,
  // so focus must land inside the overlay and restore to the opener on unmount.
  const collapseRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null
    collapseRef.current?.focus()
    return () => opener?.focus?.()
  }, [])

  const isUser = speaker === "user"
  const label = micActive
    ? `I'm listening… What's on your mind?`
    : `${agentLabel} voice paused`

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Voice session — ${label}`}
      data-voice-orb=""
      className="fixed inset-0 z-50 flex items-center justify-center bg-[radial-gradient(circle_at_center,#1a2a66_0%,#0f1738_58%,#0a1028_100%)] sm:p-6"
    >
      {/* Desktop caps the surface while mobile remains full-bleed. */}
      <div className="relative flex h-full w-full max-w-full flex-col items-center justify-center overflow-hidden sm:h-[560px] sm:w-[900px] sm:rounded-2xl">
        <button
          ref={collapseRef}
          type="button"
          onClick={onExitVoice}
          aria-label="Exit voice mode"
          className="absolute right-4 top-4 z-10 flex h-9 w-9 items-center justify-center rounded-full text-[rgba(255,255,255,0.6)] transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50"
        >
          <X className="h-5 w-5" aria-hidden />
        </button>

        <div
          aria-hidden
          data-voice-orb-circle=""
          data-voice-orb-reactive={amplitude != null ? "analyser" : "keyframe"}
          className={cn(
            "pointer-events-none relative z-0 h-[220px] w-[220px] rounded-full sm:h-[280px] sm:w-[280px]",
            isUser ? "gv-orb-user" : "gv-orb-agent",
          )}
          style={{
            backgroundImage: isUser
              ? "radial-gradient(circle at 35% 30%, #34d399, #16a374 55%, #0f5132 100%)"
              : "radial-gradient(circle at 35% 30%, #f2f2f0, #b9b9b6 55%, #6b6b68 100%)",
            transform:
              amplitude != null
                ? `scale(${(1 + Math.min(1, Math.max(0, amplitude)) * 0.12).toFixed(3)})`
                : undefined,
            transition: amplitude != null ? "transform 80ms linear" : undefined,
          }}
        />

        <div className="pointer-events-none mt-8 text-center text-white">
          <p className="text-4xl font-semibold leading-tight">{label}</p>
          <p className="mt-2 text-base text-white/70">
            {isUser ? `${agentLabel} voice channel is live` : `${agentLabel} is replying`}
          </p>
        </div>

        <div className="mt-10 flex items-center rounded-full border border-white/15 bg-white/10 p-1.5 backdrop-blur-sm">
          <button
            type="button"
            onClick={onExitVoice}
            aria-label="Exit voice mode"
            className="flex h-14 w-14 items-center justify-center rounded-full text-white/80 transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50"
          >
            <X className="h-6 w-6" aria-hidden />
          </button>
          <button
            type="button"
            onClick={onMicToggle}
            aria-label={micActive ? "Pause microphone" : "Resume microphone"}
            className={cn(
              "ml-2 flex h-14 w-14 items-center justify-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50",
              micActive
                ? "bg-white/15 text-white hover:bg-white/20"
                : "bg-[#16a374] text-white hover:bg-[#128a63]",
            )}
          >
            {micActive ? <Mic className="h-6 w-6" aria-hidden /> : <MicOff className="h-6 w-6" aria-hidden />}
          </button>
        </div>
      </div>
    </div>
  )
}
