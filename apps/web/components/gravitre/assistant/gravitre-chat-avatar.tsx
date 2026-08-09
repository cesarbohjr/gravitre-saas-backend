"use client"

import Image from "next/image"
import { motion, useReducedMotion } from "framer-motion"

import { cn } from "@/lib/utils"
import { AgentIdentityAvatar } from "@/components/gravitre/agent-identity-avatar"
import type { AgentIdentity, AgentIdentityInput } from "@/lib/agent-identity"

export type GravitreAvatarState = "idle" | "thinking" | "searching" | "speaking"

/**
 * GravitreChatAvatar — the ONE assistant avatar for every chat surface.
 *
 * Identity and state compose here rather than competing. Before this, the
 * transcript took a pre-rendered `assistantAvatar: ReactNode`, so a department
 * chat passing `<AgentIdentityAvatar>` *replaced* the stateful avatar wholesale:
 * main chat animated but looked generic, department chat carried identity but
 * could never show thinking/speaking. That prop was the escape hatch that let
 * the two surfaces drift — the fourth such drift in this program — so identity
 * now arrives as DATA (`identity` / `agent`) and this component owns rendering.
 *
 * The identity layer is not reimplemented: when an agent is supplied it renders
 * the existing `AgentIdentityAvatar`, keeping exactly one implementation of
 * "what an agent looks like" (gradient, icon, avatar image, glow). This
 * component adds only the state layer on top. A named agent therefore keeps its
 * real assigned icon and color while animating; the default assistant uses the
 * Gravitre mark. Same structure, same motion, differing only in identity —
 * which is the Part C consistency requirement stated as code.
 *
 * States map to real pipeline signals, never a decorative loop:
 *   idle       — nothing in flight
 *   thinking   — model reasoning / before first token (`showWaiting`)
 *   searching  — a tool call is in flight (invocation `state === "call"`)
 *   speaking   — TTS is actively playing this message
 *
 * Two deliberate deviations from the handoff, both to fit shipped conventions:
 *
 *  1. The circle is 36px, not 32px, matching the user avatar opposite it so both
 *     sides of the thread carry equal weight. The handoff's 50% mark-to-circle
 *     ratio is preserved exactly at 18px in 36px.
 *
 *  2. It reuses `gravitre-mark-white.png` rather than adding
 *     `gravitre-mark-alpha.png` — same glyph cropped to its ink bounds, and
 *     because the circle is dark in both themes a white mark needs no per-theme
 *     tint. One mark asset stays the source of truth.
 */
export function GravitreChatAvatar({
  state = "idle",
  identity,
  agent,
  className,
  title = "Gravitre AI is thinking",
}: {
  state?: GravitreAvatarState
  /** Resolved agent identity — renders that agent's real icon and color. */
  identity?: AgentIdentity
  /** Raw agent record, resolved through the shared identity system. */
  agent?: AgentIdentityInput
  className?: string
  /** Announced while `state` is "thinking" or "searching". */
  title?: string
}) {
  const reduceMotion = useReducedMotion()
  const isThinking = state === "thinking"
  const isSearching = state === "searching"
  const isSpeaking = state === "speaking"
  // Both states mean "work is happening", so they share the halo and the
  // breathing scale; only the glyph treatment differs.
  const isBusy = isThinking || isSearching
  const hasIdentity = Boolean(identity || agent)

  return (
    <div
      className={cn(
        "relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full",
        // A named agent's own gradient is supplied by AgentIdentityAvatar below,
        // so only the default assistant paints its own background here.
        !hasIdentity && (isSpeaking ? "bg-primary" : "bg-assistant-avatar"),
        !hasIdentity && "text-assistant-avatar-foreground",
        "transition-colors duration-300",
        className,
      )}
      // Only in-progress states are live regions: they communicate progress a
      // screen-reader user would otherwise miss. Speaking is already audible.
      {...(isBusy
        ? { role: "status" as const, "aria-live": "polite" as const, "aria-label": title }
        : {})}
    >
      {/* Thinking / searching: the handoff's `gv-glow` — a soft 6px halo that
          pulses rather than an expanding ring. An earlier ring-2 scaled to 1.35
          read as a pale disc and washed the circle out; box-shadow spreads
          outside the border box, so it stays subtle and costs no layout. */}
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

      {/* Searching extends the handoff's rotation motif rather than inventing a
          motif: a single sweeping arc traced on the rim by a conic gradient
          masked to a 2px ring. It sits outside the glyph, so the agent's own
          icon stays fully visible and identity is never traded for state. */}
      {isSearching && !reduceMotion ? (
        <motion.span
          aria-hidden
          className="pointer-events-none absolute -inset-[3px] rounded-full"
          style={{
            background:
              "conic-gradient(from 0deg, transparent 0deg, transparent 250deg, rgba(22,163,116,0.9) 340deg, transparent 360deg)",
            // Mask the filled cone down to a rim, so only the arc shows.
            WebkitMask: "radial-gradient(farthest-side, transparent calc(100% - 2px), #000 calc(100% - 2px))",
            mask: "radial-gradient(farthest-side, transparent calc(100% - 2px), #000 calc(100% - 2px))",
          }}
          animate={{ rotate: 360 }}
          transition={{ duration: 1.1, repeat: Number.POSITIVE_INFINITY, ease: "linear" }}
        />
      ) : null}

      {isSpeaking ? (
        // Speaking: three waveform bars, the handoff's `gv-bar1/2/3`.
        //
        // For a NAMED agent the identity gradient lives on the inner element the
        // bars replace, so without a backdrop the white bars landed on the light
        // card and were nearly invisible. Screenshot review caught this; the bar
        // count assertion passed regardless, since counting elements says nothing
        // about contrast. The agent's own gradient is therefore reapplied here as
        // a filled disc, keeping identity visible AND the bars legible.
        <span
          aria-hidden
          className={cn(
            "z-10 flex items-end gap-[2.5px]",
            hasIdentity && "text-white drop-shadow",
          )}
        >
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
          // Breathing while busy; idle is completely static.
          animate={isBusy && !reduceMotion ? { scale: [1, 1.12, 1], opacity: [0.9, 1, 0.9] } : {}}
          transition={
            isBusy && !reduceMotion
              ? { duration: 1.6, repeat: Number.POSITIVE_INFINITY, ease: "easeInOut" }
              : { duration: 0 }
          }
          className="flex items-center justify-center"
        >
          {hasIdentity ? (
            // Reuses the shared identity avatar so there is exactly one
            // implementation of an agent's appearance. h-full w-full makes it
            // adopt this wrapper's 36px rather than its own size scale.
            <AgentIdentityAvatar
              identity={identity}
              agent={agent}
              size="sm"
              className="h-full w-full shadow-none"
            />
          ) : (
            <Image
              src="/images/gravitre-mark-white.png"
              alt=""
              aria-hidden
              width={1030}
              height={572}
              // 18px = 50% of the 36px circle, the handoff's mark-to-circle
              // ratio. The mark is wider than tall, so width drives it and
              // height follows the aspect ratio through object-contain.
              className="w-[18px] object-contain"
              priority={false}
            />
          )}
        </motion.div>
      )}
    </div>
  )
}
