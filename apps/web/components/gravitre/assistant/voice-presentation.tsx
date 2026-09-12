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
 * Canonical exports (UI 2.0 Pilot E):
 *   GravitreWave          — alias of GravitreVoiceWaveform (keep both names)
 *   GravitreOrb           — orb circle only; VoiceOrbTakeover composes it
 *   VoiceStateVisualizer  — maps VoicePresenceState → Wave (no second DOM path)
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
 *
 * Duplex presence states are **client UX** — not PSTN VoiceSessionStatus parity.
 */

import { useEffect, useRef, useState } from "react"
import { Mic, MicOff, Minimize2, Volume2, X } from "lucide-react"
import { cn } from "@/lib/utils"
import type { VoicePresenceState } from "@/components/gravitre/assistant/voice-session-presence"
import { useElementSize } from "@/hooks/use-element-size"
import { orbBloomPx, voiceOrbSize } from "@/lib/voice-orb-sizing"

/**
 * Who currently holds the floor. This maps 1:1 onto the presence state the chat
 * surfaces already track (`listening` = mic open = the user; `speaking` = TTS
 * playing = the agent), so no new state detection is introduced.
 */
export type VoiceSpeaker = "user" | "agent"

/** Resolved wave props from a duplex presence state (client-only). */
export type VoiceVisualizerResolved = {
  speaker: VoiceSpeaker
  active: boolean
  /** Whether the live floor is open (listening / thinking / speaking / …). */
  liveFloor: boolean
}

/**
 * Map client VoicePresenceState → Wave props. Shared by presence strip and any
 * future consumer so speaker/active never fork per surface.
 */
export function resolveVoiceVisualizer(
  state: VoicePresenceState,
): VoiceVisualizerResolved {
  const liveFloor =
    state === "listening" ||
    state === "understanding" ||
    state === "thinking" ||
    state === "speaking" ||
    state === "interrupted"
  const speaker: VoiceSpeaker =
    state === "speaking" || state === "thinking" ? "agent" : "user"
  return { speaker, active: liveFloor, liveFloor }
}

/** Per-speaker motion and color, verbatim from the handoff. */
const WAVE_DURATION: Record<VoiceSpeaker, string> = {
  // The user's own voice reads as immediate; the agent's is calmer and slower so
  // the two are distinguishable without reading the label. Advanced Design: breathe.
  user: "0.75s",
  agent: "1.35s",
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
      data-gravitre-wave=""
      className={cn(
        "flex items-center gap-[3px]",
        // Bars are `background-color: currentColor`, so speaker color is set here
        // once rather than on each of the seven.
        !active
          ? "text-[color:var(--gv-voice-idle)] dark:text-[color:var(--gv-voice-idle-dark)]"
          : speaker === "user"
            ? "text-[color:var(--gv-voice-user)]"
            : "text-[color:var(--gv-voice-agent)] dark:text-[color:var(--gv-voice-agent-fg)]",
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
            style={
              height
                ? {
                    height,
                    animation: "none",
                    transition: "height 160ms cubic-bezier(0.22, 1, 0.36, 1)",
                  }
                : undefined
            }
          />
        )
      })}
    </span>
  )
}

/** Canonical Wave name (Pilot E). Same implementation as GravitreVoiceWaveform. */
export const GravitreWave = GravitreVoiceWaveform

/**
 * Maps a duplex presence state onto the shared Wave — no second bar DOM.
 * Idle/error omit bars (callers that need icons wrap this or branch themselves).
 */
export function VoiceStateVisualizer({
  state,
  levels,
  compact = true,
  className,
}: {
  state: VoicePresenceState
  levels?: number[] | null
  compact?: boolean
  className?: string
}) {
  const { speaker, active, liveFloor } = resolveVoiceVisualizer(state)
  if (!liveFloor && state !== "idle") {
    // Error / disconnected: no wave — presence strip owns icons for those.
    return null
  }
  if (state === "idle") {
    return null
  }
  return (
    <span data-voice-state-visualizer={state} className="contents">
      <GravitreWave
        speaker={speaker}
        active={active}
        compact={compact}
        levels={levels}
        className={className}
      />
    </span>
  )
}

/**
 * Orb circle only — the visual primitive. VoiceOrbTakeover owns chrome (exit,
 * mic, labels). Never fork a MarketingGravitreOrb; import this.
 */
export function GravitreOrb({
  speaker,
  amplitude,
  className,
  compact = false,
  diameter,
}: {
  speaker: VoiceSpeaker
  /** Optional AnalyserNode peak 0–1 — scales the orb when present. */
  amplitude?: number | null
  className?: string
  /** Smaller circle for containers as narrow as 400px (float, mobile sheet). */
  compact?: boolean
  /**
   * Measured diameter in px, from the container the orb actually sits in.
   *
   * When present it replaces the `compact` classes entirely. Those were two fixed
   * pairs stepped by the `sm:` breakpoint -- a *viewport* media query -- so a
   * 400px-wide float window on a wide monitor rendered the large orb. `compact`
   * remains the fallback for callers that have nothing to measure yet (first
   * paint, and the 36px launcher disc which sizes itself by className).
   */
  diameter?: number | null
}) {
  const isUser = speaker === "user"
  const measured = typeof diameter === "number" && Number.isFinite(diameter) && diameter > 0
  // EMA dampening so amplitude breathes instead of twitching (Advanced Design §9).
  const smoothedRef = useRef(0)
  const [smoothed, setSmoothed] = useState(0)

  useEffect(() => {
    if (amplitude == null || Number.isNaN(amplitude)) {
      smoothedRef.current = 0
      setSmoothed(0)
      return
    }
    const target = Math.min(1, Math.max(0, amplitude))
    const next = smoothedRef.current * 0.82 + target * 0.18
    smoothedRef.current = next
    setSmoothed(next)
  }, [amplitude])

  return (
    <div
      aria-hidden
      data-voice-orb-circle=""
      data-gravitre-orb=""
      data-voice-orb-reactive={amplitude != null ? "analyser" : "keyframe"}
      data-voice-orb-sizing={measured ? "container" : "class"}
      className={cn(
        "pointer-events-none relative z-0 rounded-full",
        // Only fall back to the fixed pairs when there is no measurement.
        !measured &&
          (compact
            ? "h-[104px] w-[104px] sm:h-[128px] sm:w-[128px]"
            : "h-[220px] w-[220px] sm:h-[280px] sm:w-[280px]"),
        isUser ? "gv-orb-user" : "gv-orb-agent",
        className,
      )}
      style={{
        ...(measured
          ? {
              height: `${diameter}px`,
              width: `${diameter}px`,
              // The pulse bloom used to be a fixed spread, which is unremarkable
              // around a 280px orb and overflows a small container around a 96px
              // one. Proportional, it scales with the circle.
              ["--gv-orb-bloom" as string]: `${orbBloomPx(diameter!)}px`,
            }
          : null),
        backgroundImage: isUser
          ? "radial-gradient(circle at 35% 30%, var(--gv-voice-user-bright), var(--gv-voice-user) 55%, var(--gv-voice-user-deep) 100%)"
          : "radial-gradient(circle at 35% 30%, var(--gv-voice-agent-light), var(--gv-voice-agent-mid) 55%, var(--gv-voice-idle-dark) 100%)",
        transform:
          amplitude != null
            ? `scale(${(1 + smoothed * 0.1).toFixed(3)})`
            : undefined,
        transition:
          amplitude != null
            ? "transform 180ms cubic-bezier(0.22, 1, 0.36, 1)"
            : undefined,
      }}
    />
  )
}

export type VoiceOrbPhase =
  | "blocked"
  | "muted"
  | "listening"
  | "replying"
  | "ended"
  | "failed"
  | "reconnecting"

/**
 * Resolve the orb's heading and subtitle from ONE phase.
 *
 * Previously the heading read from `micActive` and the subtitle from `speaker`,
 * two unrelated inputs. A muted-but-connected session satisfied both branches at
 * once and rendered "<agent> voice paused" directly above "<agent> voice channel
 * is live". Exported so that contradiction is testable without a DOM.
 */
export function resolveVoiceOrbCopy({
  playbackBlocked = false,
  micMuted = false,
  micActive = true,
  speaker,
  sessionLive = true,
  agentLabel = "Gravitre",
  activityLabel,
  presence,
  failureReason,
}: {
  playbackBlocked?: boolean
  micMuted?: boolean
  micActive?: boolean
  speaker: VoiceSpeaker
  sessionLive?: boolean
  agentLabel?: string
  activityLabel?: string | null
  presence?: string | null
  failureReason?: string | null
}): { phase: VoiceOrbPhase; label: string; subtitle: string } {
  const isUser = speaker === "user"
  // Failure outranks the mic/session booleans. Both "error" and "disconnected"
  // leave micActive and sessionLive false, which used to land on "ended" -- so a
  // session that failed to connect rendered the same calm "voice ended / tap the
  // mic to start talking again" as one the user deliberately hung up. That is
  // why a real failure looked like nothing happening: the surface had no way to
  // say a session had died, or why.
  const phase: VoiceOrbPhase = playbackBlocked
    ? "blocked"
    : presence === "error"
      ? "failed"
      : presence === "disconnected"
        ? "reconnecting"
        : micMuted
          ? "muted"
          : micActive
            ? "listening"
            : !isUser
              ? "replying"
              : sessionLive
                ? "listening"
                : "ended"

  switch (phase) {
    case "blocked":
      return {
        phase,
        label: "Sound is blocked",
        subtitle: "Your browser blocked audio playback. Tap below to enable sound.",
      }
    case "muted":
      return {
        phase,
        label: "Microphone muted",
        subtitle: `${agentLabel} can't hear you — tap the mic to unmute`,
      }
    case "replying": {
      const status = activityLabel?.trim() || `${agentLabel} is replying`
      return { phase, label: status, subtitle: status }
    }
    case "listening":
      return {
        phase,
        label: "I'm listening… What's on your mind?",
        subtitle: `${agentLabel} voice channel is live`,
      }
    case "failed":
      return {
        phase,
        label: "Voice couldn't connect",
        // The server's own explanation when there is one. Falling back to advice
        // rather than an error code, since a code tells the person nothing they
        // can act on.
        subtitle: failureReason?.trim() || "Tap the mic to try again",
      }
    case "reconnecting":
      return {
        phase,
        label: "Reconnecting…",
        subtitle: `The voice channel dropped — ${agentLabel} is trying again`,
      }
    default:
      return {
        phase,
        label: `${agentLabel} voice ended`,
        subtitle: "Tap the mic to start talking again",
      }
  }
}

/**
 * Component 2 — orb voice surface.
 *
 * Hit areas are siblings in a stacking order, never nested: the centre tap layer
 * is a button covering the surface, with "✕" and the bottom control painted above
 * it. Nesting them would be invalid HTML and, worse, a tap on "✕" would also
 * fire the collapse handler underneath — exiting voice mode AND collapsing.
 *
 * Two variants:
 * - `fullscreen` fixes to the viewport and is a modal dialog.
 * - `contained` fills its positioned parent instead, for the float window, docked
 *   shell and mobile sheet. Those are as small as 400×420, so a viewport-fixed
 *   overlay would swallow the whole screen from inside a small window. Contained is
 *   deliberately NOT `aria-modal`: content behind it stays reachable.
 */
export function VoiceOrbTakeover({
  speaker,
  agentLabel = "Gravitre",
  onExitVoice,
  onMicToggle,
  onMinimize,
  micActive = true,
  micMuted = false,
  sessionLive = true,
  variant = "fullscreen",
  amplitude,
  playbackBlocked = false,
  onEnableSound,
  activityLabel,
  presence,
  failureReason,
}: {
  speaker: VoiceSpeaker
  agentLabel?: string
  /** Raw duplex presence, so a dead session can say so instead of "ended". */
  presence?: string | null
  /** The server's explanation, when it sent one. */
  failureReason?: string | null
  /** Leave voice mode entirely, back to typed text. */
  onExitVoice: () => void
  /** Mute/unmute the mic while the call stays connected. */
  onMicToggle?: () => void
  micActive?: boolean
  /** Mic muted with the session still connected — not the same as ended. */
  micMuted?: boolean
  /** A duplex session is connected (muted or not). */
  sessionLive?: boolean
  /**
   * Collapse back to the composer waveform while KEEPING the call connected.
   * Absent means no minimize affordance is rendered — which is how fullscreen
   * shipped with only "end the call" as a way out.
   */
  onMinimize?: () => void
  variant?: "fullscreen" | "contained"
  /** Optional AnalyserNode peak 0–1 — scales the orb when present. */
  amplitude?: number | null
  /**
   * Browser autoplay gate tripped (a cold/slow turn outlived the "Talk" tap's
   * user-activation window). This is the ONLY surface visible while voice mode
   * owns the screen — a banner rendered behind this fixed overlay is invisible,
   * which is how "no audio, no error" happened. Must render its own recovery here.
   */
  playbackBlocked?: boolean
  /** Fresh user gesture to retry the held-back reply and unlock future turns. */
  onEnableSound?: () => void
  activityLabel?: string | null
}) {
  const fullscreen = variant === "fullscreen"

  // Escape gets out of a surface that covers the viewport. Prefer minimizing --
  // keeping the call and returning to the composer beats hanging up. Contained
  // variants do not own the screen, so they must not steal Escape from the dialog
  // or sheet hosting them.
  useEffect(() => {
    if (!fullscreen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation()
        if (onMinimize) onMinimize()
        else onExitVoice()
      }
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [fullscreen, onExitVoice, onMinimize])

  // `aria-modal="true"` asserts that everything behind this overlay is unreachable,
  // so focus must land inside the overlay and restore to the opener on unmount.
  // Contained variants are not modal and must not move focus.
  const collapseRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    if (!fullscreen) return
    const opener = document.activeElement as HTMLElement | null
    collapseRef.current?.focus()
    return () => opener?.focus?.()
  }, [fullscreen])

  const { label, subtitle } = resolveVoiceOrbCopy({
    presence,
    failureReason,
    playbackBlocked,
    micMuted,
    micActive,
    speaker,
    sessionLive,
    agentLabel,
    activityLabel,
  })

  // Contained surfaces can be as small as 400x420, so type and controls step down
  // with the variant.
  //
  // The orb no longer does. It used to share this coarse switch, and the step
  // between its two fixed sizes was the `sm:` *viewport* media query, so a 400px
  // float window on a wide monitor rendered the large orb inside a small
  // container. It is now measured from this element -- a real ResizeObserver on
  // the surface itself, which is the container that actually constrains it.
  const controlSize = fullscreen ? "h-14 w-14" : "h-11 w-11"
  const controlIcon = fullscreen ? "h-6 w-6" : "h-5 w-5"

  const [surfaceEl, setSurfaceEl] = useState<HTMLDivElement | null>(null)
  const surface = useElementSize(surfaceEl)
  const orb = voiceOrbSize({
    containerWidth: surface.width,
    containerHeight: surface.height,
    variant: fullscreen ? "fullscreen" : "contained",
    amplitude,
  })

  return (
    <div
      ref={setSurfaceEl}
      // Contained is not modal: it fills its own parent and leaves the rest of the
      // window usable, so claiming aria-modal here would lie to screen readers.
      role={fullscreen ? "dialog" : "group"}
      aria-modal={fullscreen ? true : undefined}
      aria-label={`Voice session — ${label}`}
      data-voice-orb=""
      data-voice-orb-variant={variant}
      className={cn(
        "flex items-center justify-center bg-[radial-gradient(circle_at_center,var(--gv-voice-orb-backdrop-mid)_0%,var(--gv-voice-orb-backdrop-deep)_58%,var(--gv-voice-orb-backdrop-edge)_100%)]",
        fullscreen ? "fixed inset-0 z-50 sm:p-6" : "absolute inset-0 z-30 rounded-[inherit] p-3",
      )}
    >
      {/* Desktop caps the surface while mobile remains full-bleed. */}
      <div
        className={cn(
          "relative flex h-full w-full max-w-full flex-col items-center justify-center overflow-hidden",
          fullscreen ? "sm:h-[560px] sm:w-[900px] sm:rounded-2xl" : "gap-1",
        )}
      >
        <div className="absolute right-2 top-2 z-10 flex items-center gap-1 sm:right-4 sm:top-4">
          {onMinimize ? (
            <button
              ref={collapseRef}
              type="button"
              onClick={onMinimize}
              aria-label="Minimize voice — keeps the call connected"
              title="Minimize voice (call stays connected)"
              className="flex h-9 w-9 items-center justify-center rounded-full text-[rgba(255,255,255,0.6)] transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50"
            >
              <Minimize2 className="h-5 w-5" aria-hidden />
            </button>
          ) : null}
          <button
            // Focus lands on minimize when it exists, so the first tab stop is the
            // non-destructive way out rather than hanging up.
            ref={onMinimize ? undefined : collapseRef}
            type="button"
            onClick={onExitVoice}
            aria-label="End voice session"
            title="End voice session"
            className="flex h-9 w-9 items-center justify-center rounded-full text-[rgba(255,255,255,0.6)] transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50"
          >
            <X className="h-5 w-5" aria-hidden />
          </button>
        </div>

        {/*
          A null diameter means the container has no room for a legible orb, which
          is the minimized case: show nothing here rather than an illegible disc.
          `compact` stays as the pre-measurement fallback for the first paint.
        */}
        {orb.diameter !== 0 ? (
          <GravitreOrb
            speaker={speaker}
            amplitude={amplitude}
            compact={!fullscreen}
            diameter={orb.diameter}
          />
        ) : null}

        <div
          className={cn(
            "pointer-events-none text-center text-white",
            fullscreen ? "mt-8" : "mt-4 px-2",
          )}
        >
          <p
            className={cn(
              "font-semibold leading-tight",
              fullscreen ? "text-4xl" : "text-lg sm:text-xl",
            )}
          >
            {label}
          </p>
          <p className={cn("text-white/70", fullscreen ? "mt-2 text-base" : "mt-1 text-xs sm:text-sm")}>
            {subtitle}
          </p>
        </div>

        {playbackBlocked ? (
          <button
            type="button"
            onClick={onEnableSound}
            className={cn(
              "relative z-10 flex items-center gap-2 rounded-full border border-white/25 bg-white/15 px-5 py-2.5 font-medium text-white backdrop-blur-sm transition-colors hover:bg-white/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50",
              fullscreen ? "mt-6 text-sm" : "mt-3 text-xs",
            )}
          >
            <Volume2 className="h-4 w-4" aria-hidden />
            Enable sound
          </button>
        ) : null}

        <div
          className={cn(
            "flex items-center rounded-full border border-white/15 bg-white/10 p-1.5 backdrop-blur-sm",
            fullscreen ? "mt-10" : "mt-4",
          )}
        >
          <button
            type="button"
            onClick={onExitVoice}
            aria-label="End voice session"
            className={cn(
              "flex items-center justify-center rounded-full text-white/80 transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50",
              controlSize,
            )}
          >
            <X className={controlIcon} aria-hidden />
          </button>
          <button
            type="button"
            onClick={onMicToggle}
            aria-label={micMuted ? "Unmute microphone" : "Mute microphone"}
            aria-pressed={micMuted}
            className={cn(
              "ml-2 flex items-center justify-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50",
              controlSize,
              micMuted
                ? "bg-[color:var(--gv-voice-user)] text-white hover:bg-[color:var(--gv-voice-user-hover)]"
                : "bg-white/15 text-white hover:bg-white/20",
            )}
          >
            {micMuted ? (
              <MicOff className={controlIcon} aria-hidden />
            ) : (
              <Mic className={controlIcon} aria-hidden />
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
