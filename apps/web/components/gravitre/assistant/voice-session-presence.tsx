"use client"

/**
 * Compact voice-session presence strip for the agent chat composer.
 *
 * Presentation only: it renders the state the chat page already tracks and owns
 * no session, transport, or entitlement logic of its own.
 *
 * Motif: the waveform, not an orb. `gravitre-chat-avatar` already speaks with
 * three scaleY bars, so the same DNA (rounded bars, bg-current, staggered
 * easeInOut) is reused here at five bars — a wider read for a session strip
 * without introducing a second competing hero shape.
 *
 * Motion budget is three intentional motions, and idle deliberately has none so
 * a voice session that is merely open never animates in an operator's periphery:
 *   1. listening  — bars react (mic is open)
 *   2. speaking   — bars travel (agent is talking)
 *   3. error      — a single settle, then still
 */

import { motion, useReducedMotion } from "framer-motion"
import { AlertCircle, CreditCard, Mic } from "lucide-react"
import { cn } from "@/lib/utils"

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
  className?: string
}

/**
 * Five bars sharing the avatar's waveform DNA. Exported so the voice-assignment
 * preview affordance renders the same motif instead of growing a second one.
 */
export function VoiceWaveform({
  active,
  travelling,
  reduceMotion,
}: {
  active: boolean
  travelling: boolean
  reduceMotion: boolean | null
}) {
  // Listening reacts in place; speaking travels left-to-right via delay ramp.
  const heights = [7, 11, 14, 11, 7]
  return (
    <span aria-hidden className="flex items-center gap-[2.5px]">
      {heights.map((h, i) => {
        const delay = travelling ? i * 0.08 : i === 2 ? 0 : 0.15
        return (
          <motion.span
            key={i}
            className="w-[2.5px] rounded-full bg-current"
            style={{ height: h }}
            animate={
              !active || reduceMotion
                ? { scaleY: active ? 0.8 : 0.45 }
                : travelling
                  ? { scaleY: [0.4, 1, 0.4] }
                  : { scaleY: i % 2 === 0 ? [0.5, 1, 0.5] : [1, 0.45, 1] }
            }
            transition={
              !active || reduceMotion
                ? { duration: 0 }
                : { duration: 0.9, repeat: Number.POSITIVE_INFINITY, ease: "easeInOut", delay }
            }
          />
        )
      })}
    </span>
  )
}

export function VoiceSessionPresence({ state, billing = false, detail, className }: Props) {
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
          <VoiceWaveform
            active
            travelling={state === "speaking"}
            reduceMotion={reduceMotion}
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
    </motion.div>
  )
}
