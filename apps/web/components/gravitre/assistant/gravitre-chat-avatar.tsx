"use client"

import Image from "next/image"
import { motion, useReducedMotion } from "framer-motion"

import { cn } from "@/lib/utils"

export type GravitreAvatarState = "idle" | "thinking" | "speaking"

/**
 * GravitreChatAvatar — the assistant avatar for every chat window.
 *
 * Implements the three states from the design handoff (idle / thinking /
 * speaking) as a filled circle carrying the Gravitre mark.
 *
 * Two deliberate deviations from the handoff, both to fit conventions that
 * already ship:
 *
 *  1. The circle is 36px, not the handoff's 32px. 36px is the size the user
 *     avatar renders at on the opposite side of the thread, so matching it keeps
 *     both sides of the conversation at equal visual weight and avoids shifting
 *     every message row. The handoff's 16px-mark-in-32px-circle ratio (50%) is
 *     preserved exactly at 18px in 36px.
 *
 *  2. It reuses `gravitre-mark-white.png` instead of adding the handoff's
 *     `gravitre-mark-alpha.png`. That file is the same glyph already cropped to
 *     its ink bounds (987x572 vs 1030x572), and because the circle is dark in
 *     both themes a white mark needs no `filter: brightness(0) invert(1)` tint
 *     and no per-theme asset swap. One mark asset stays the source of truth.
 *
 * The filled circle also settles a question left open when the mark last sat
 * bare on the canvas: a wide, short glyph reads lighter than the solid circle
 * opposite it. Inside a filled circle the two now carry the same mass.
 */
export function GravitreChatAvatar({
  state = "idle",
  className,
  title = "Gravitre AI is thinking",
}: {
  state?: GravitreAvatarState
  className?: string
  /** Announced while `state` is "thinking". */
  title?: string
}) {
  const reduceMotion = useReducedMotion()
  const isThinking = state === "thinking"
  const isSpeaking = state === "speaking"

  return (
    <div
      className={cn(
        "relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full",
        // Speaking brightens to the brand green; idle and thinking sit on the
        // muted variant so a long thread of replies stays calm.
        isSpeaking ? "bg-primary" : "bg-assistant-avatar",
        "text-assistant-avatar-foreground transition-colors duration-300",
        className,
      )}
      // Only the thinking state is a live region: it is the one state that
      // communicates progress a screen-reader user would otherwise miss.
      {...(isThinking
        ? { role: "status" as const, "aria-live": "polite" as const, "aria-label": title }
        : {})}
    >
      {/* Thinking: the handoff's `gv-glow` — a soft 6px halo that pulses, not an
          expanding ring. An earlier ring-2 scaled to 1.35 read as a pale disc
          around the avatar and washed the circle out; box-shadow spreads outside
          the border box, so it stays subtle and still costs no layout. */}
      {isThinking && !reduceMotion ? (
        <motion.span
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-full"
          animate={{
            boxShadow: [
              "0 0 0 0 rgba(22,163,116,0.35)",
              "0 0 0 6px rgba(22,163,116,0.12)",
              "0 0 0 0 rgba(22,163,116,0.35)",
            ],
          }}
          transition={{ duration: 1.6, repeat: Number.POSITIVE_INFINITY, ease: "easeInOut" }}
        />
      ) : null}

      {isSpeaking ? (
        // Speaking: three waveform bars replace the mark.
        <span aria-hidden className="flex items-end gap-[2.5px]">
          {[0, 0.15, 0.3].map((delay, i) => (
            <motion.span
              key={delay}
              className="w-[2.5px] rounded-full bg-current"
              style={{ height: 10 }}
              animate={
                reduceMotion
                  ? { scaleY: 0.7 }
                  : { scaleY: i === 1 ? [1, 0.35, 1] : [0.45, 1, 0.45] }
              }
              transition={
                reduceMotion
                  ? { duration: 0 }
                  : {
                      duration: 0.9,
                      repeat: Number.POSITIVE_INFINITY,
                      ease: "easeInOut",
                      delay,
                    }
              }
            />
          ))}
        </span>
      ) : (
        <motion.div
          // Breathing only while thinking; idle is completely static.
          animate={isThinking && !reduceMotion ? { scale: [1, 1.12, 1], opacity: [0.9, 1, 0.9] } : {}}
          transition={
            isThinking && !reduceMotion
              ? { duration: 1.6, repeat: Number.POSITIVE_INFINITY, ease: "easeInOut" }
              : { duration: 0 }
          }
          className="flex items-center justify-center"
        >
          <Image
            src="/images/gravitre-mark-white.png"
            alt=""
            aria-hidden
            width={1030}
            height={572}
            // 18px = 50% of the 36px circle, the handoff's mark-to-circle ratio.
            // The mark is wider than tall, so width drives it and height follows
            // the aspect ratio through object-contain.
            className="w-[18px] object-contain"
            priority={false}
          />
        </motion.div>
      )}
    </div>
  )
}
