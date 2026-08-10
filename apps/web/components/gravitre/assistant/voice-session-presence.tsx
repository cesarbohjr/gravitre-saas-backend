"use client"

/**
 * Compact voice-session presence strip for the agent chat composer.
 *
 * Presentation only: it renders the state the chat page already tracks and owns
 * no session, transport, or entitlement logic of its own.
 *
 * Motif: the waveform, not an orb. The bars are the canonical
 * GravitreVoiceWaveform from `voice-presentation`, rendered at compact scale.
 * This file previously carried its OWN five-bar implementation, which drifted
 * from the seven-bar handoff spec the moment that spec landed — the same
 * duplicate-component failure this program keeps hitting. There is now one
 * waveform, scaled, not two sets of bars to keep in sync.
 *
 * Motion budget is three intentional motions, and idle deliberately has none so
 * a voice session that is merely open never animates in an operator's periphery:
 *   1. listening  — bars react (mic is open)
 *   2. speaking   — bars travel (agent is talking)
 *   3. error      — a single settle, then still
 */

import { motion, useReducedMotion } from "framer-motion"
import { AlertCircle, CreditCard, Maximize2, Mic } from "lucide-react"
import { cn } from "@/lib/utils"
import { GravitreVoiceWaveform } from "@/components/gravitre/assistant/voice-presentation"

export type VoicePresenceState = "idle" | "listening" | "speaking" | "error"

type Props = {
  state: VoicePresenceState
  /**
   * Billing-shaped failure (the shipped 402 from TTS). Renders the calm credits
   * treatment instead of a generic red server-error look. No new error code is
   * introduced — the caller maps its own response to this flag.
   */
  billing?: boolean
  /** Optional short detail line, e.g. a transcript hint or failure reason. */
  detail?: string
  /**
   * Expand to the full-screen orb, staying in voice mode. Omitted (not disabled)
   * when there is no live speaker, so the strip renders as plain status text with
   * no dead control — an inert-looking button that does nothing is worse than no
   * button, and the orb has nothing real to depict when nobody holds the floor.
   */
  onExpand?: () => void
  className?: string
}

export function VoiceSessionPresence({
  state,
  billing = false,
  detail,
  onExpand,
  className,
}: Props) {
  const reduceMotion = useReducedMotion()

  const isError = state === "error"
  // Billing is a wait-for-credits condition, not a fault: amber, never red.
  const tone = isError
    ? billing
      ? "text-warning"
      : "text-muted-foreground"
    : state === "idle"
      ? "text-muted-foreground"
      : "text-success"

  const label = isError
    ? billing
      ? "Voice paused — credits needed"
      : "Voice unavailable right now"
    : state === "listening"
      ? "Listening"
      : state === "speaking"
        ? "Agent speaking"
        : "Voice mode on"

  return (
    <motion.div
      // Error settles once and stops; the other states never move the container.
      initial={isError && !reduceMotion ? { y: -2, opacity: 0 } : false}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
      // Announce the state change without stealing focus from the composer.
      role="status"
      aria-live="polite"
      className={cn(
        "flex items-center gap-2 rounded-lg border px-2.5 py-1.5",
        isError && billing
          ? "border-warning/30 bg-warning/[0.06]"
          : isError
            ? "border-border/70 bg-muted/40"
            : state === "idle"
              ? "border-border/70 bg-muted/30"
              : "border-success/25 bg-success/[0.06]",
        className,
      )}
    >
      <span className={cn("flex shrink-0 items-center", tone)}>
        {isError ? (
          billing ? (
            <CreditCard className="h-3.5 w-3.5" aria-hidden />
          ) : (
            <AlertCircle className="h-3.5 w-3.5" aria-hidden />
          )
        ) : state === "idle" ? (
          <Mic className="h-3.5 w-3.5" aria-hidden />
        ) : (
          <GravitreVoiceWaveform
            // Same seven-bar component the composer and orb use, rendered at icon
            // scale. Previously this was a separate five-bar implementation, which
            // is precisely the second-waveform drift this pass exists to remove.
            speaker={state === "speaking" ? "agent" : "user"}
            compact
          />
        )}
      </span>

      <span className="min-w-0 flex-1">
        <span className={cn("block truncate text-xs font-medium leading-tight", tone)}>{label}</span>
        {detail ? (
          <span className="mt-0.5 block truncate text-[11px] leading-tight text-muted-foreground">
            {detail}
          </span>
        ) : null}
      </span>

      {/*
        Expand affordance. A real <button> inside the strip rather than making the
        strip itself clickable: the container is the `role="status"` live region,
        and turning a live region into a button both breaks the announcement and
        makes every state change sound like an interactive control appearing.
      */}
      {onExpand ? (
        <button
          type="button"
          onClick={onExpand}
          className="flex shrink-0 items-center gap-1 rounded-md px-1.5 py-1 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Maximize2 className="h-3 w-3" aria-hidden />
          Expand
        </button>
      ) : null}
    </motion.div>
  )
}
