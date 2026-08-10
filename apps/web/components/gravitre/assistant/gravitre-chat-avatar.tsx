"use client"

import Image from "next/image"
import { motion, useReducedMotion } from "framer-motion"

import { cn } from "@/lib/utils"

export type GravitreAvatarState = "idle" | "thinking" | "searching" | "speaking"

/**
 * GravitreChatAvatar — the ONE assistant avatar for every chat surface.
 *
 * Product rule (2026-08): the disc is always the animated Gravitre mark — idle,
 * thinking (breathe + glow), searching (rim sweep), speaking (bars). Main `/ai`
 * and department agent chats share this visual. What differs between surfaces is
 * the *label* (persona / agent name), voice, and admin-configured personality —
 * not a per-agent icon disc in the transcript.
 *
 * Earlier, passing `agent` swapped in `AgentIdentityAvatar` and produced the
 * orange sparkles “Friendly Assistant” disc (and department-colored icons). That
 * violated the handoff in `design_handoff_avatar/reference.html`. Agent hub
 * cards may still use identity avatars; the *chat thread* does not.
 *
 * States map to real pipeline signals, never a decorative loop:
 *   idle       — nothing in flight
 *   thinking   — model reasoning / before first token (`showWaiting`)
 *   searching  — a tool call is in flight (invocation `state === "call"`)
 *   speaking   — TTS is actively playing this message
 *
 * Deviations from the handoff, kept to match shipped chat chrome:
 *   1. Circle is 36px (not 32px) to match the user avatar opposite it.
 *   2. Uses `gravitre-mark-white.png` (same glyph; dark disc in both themes).
 */
export function GravitreChatAvatar({
  state = "idle",
  className,
  title = "Gravitre is thinking",
}: {
  state?: GravitreAvatarState
  className?: string
  /** Announced while `state` is "thinking" or "searching". */
  title?: string
}) {
  const reduceMotion = useReducedMotion()
  const isThinking = state === "thinking"
  const isSearching = state === "searching"
  const isSpeaking = state === "speaking"
  const isBusy = isThinking || isSearching

  return (
    <div
      className={cn(
        "relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full",
        isSpeaking ? "bg-primary" : "bg-assistant-avatar",
        "text-assistant-avatar-foreground",
        "transition-colors duration-300",
        className,
      )}
      {...(isBusy
        ? { role: "status" as const, "aria-live": "polite" as const, "aria-label": title }
        : {})}
    >
      {/* Thinking / searching: handoff `gv-glow` — soft 6px halo pulse. */}
      {isBusy && !reduceMotion ? (
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

      {/* Searching: sweeping rim arc; mark stays visible underneath. */}
      {isSearching && !reduceMotion ? (
        <motion.span
          aria-hidden
          className="pointer-events-none absolute -inset-[3px] rounded-full"
          style={{
            background:
              "conic-gradient(from 0deg, transparent 0deg, transparent 250deg, rgba(22,163,116,0.9) 340deg, transparent 360deg)",
            WebkitMask: "radial-gradient(farthest-side, transparent calc(100% - 2px), #000 calc(100% - 2px))",
            mask: "radial-gradient(farthest-side, transparent calc(100% - 2px), #000 calc(100% - 2px))",
          }}
          animate={{ rotate: 360 }}
          transition={{ duration: 1.1, repeat: Number.POSITIVE_INFINITY, ease: "linear" }}
        />
      ) : null}

      {isSpeaking ? (
        <span aria-hidden className="z-10 flex items-end gap-[2.5px] text-white">
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
          animate={isBusy && !reduceMotion ? { scale: [1, 1.12, 1], opacity: [0.9, 1, 0.9] } : {}}
          transition={
            isBusy && !reduceMotion
              ? { duration: 1.6, repeat: Number.POSITIVE_INFINITY, ease: "easeInOut" }
              : { duration: 0 }
          }
          className="flex h-full w-full items-center justify-center"
        >
          <Image
            src="/images/gravitre-mark-white.png"
            alt=""
            aria-hidden
            width={1030}
            height={572}
            className="w-[18px] object-contain"
            priority={false}
          />
        </motion.div>
      )}
    </div>
  )
}
