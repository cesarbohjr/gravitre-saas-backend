"use client"

/**
 * GravitreIntelligenceCore — Relational Topology (Creative Experience System 1.0).
 * Geometry changes by state; not a spinning orb. In-flow for 3×3 grid layout.
 */

import { AnimatePresence, motion } from "framer-motion"
import { LogoSVG } from "@/components/marketing/nodus/logo"
import { topologyForCoreState } from "@/components/marketing/creative/primitives/relational-topology"
import { CREATIVE_TOKENS } from "@/components/marketing/creative/core/tokens"
import { CORE_STATE_LABEL, type CoreState } from "./types"
import { cn } from "@/lib/utils"

export function GravitreIntelligenceCore({
  state = "idle",
  reduced = false,
  learnedEdgeCount = 0,
}: {
  state?: CoreState
  reduced?: boolean
  /** Session permanent relationships — visual density cue after LEARN */
  learnedEdgeCount?: number
}) {
  const label = CORE_STATE_LABEL[state]
  const resolved = state === "verified" || state === "learned"
  const layout = topologyForCoreState(state === "idle" && learnedEdgeCount > 0 ? "learned" : state)

  return (
    <div className="relative flex flex-col items-center gap-2">
      <motion.div
        initial={false}
        animate={{ scale: resolved ? 1.02 : 1 }}
        transition={{ duration: 0.35 }}
        className={cn(
          "relative flex h-[7.25rem] w-[7.25rem] items-center justify-center overflow-hidden rounded-2xl border bg-white shadow-[var(--shadow-aceternity)]",
          resolved
            ? "border-[color:var(--color-brand,#16a374)]"
            : "border-[color:var(--color-line,#eaedf1)]",
        )}
      >
        <svg viewBox="0 0 80 72" className="absolute inset-0 h-full w-full" aria-hidden>
          {layout.edges.map(([a, b], i) => {
            const pa = layout.nodes[a]
            const pb = layout.nodes[b]
            if (!pa || !pb) return null
            const isOutbound =
              layout.outboundIndices.includes(a) || layout.outboundIndices.includes(b)
            const isInbound =
              layout.inboundIndex === a || layout.inboundIndex === b
            return (
              <motion.line
                key={`e-${state}-${i}`}
                x1={pa.x}
                y1={pa.y}
                x2={pb.x}
                y2={pb.y}
                stroke={
                  isInbound
                    ? CREATIVE_TOKENS.signal
                    : isOutbound
                      ? CREATIVE_TOKENS.action
                      : resolved
                        ? CREATIVE_TOKENS.action
                        : "color-mix(in srgb, var(--g-intelligence) 45%, #c5c9d0)"
                }
                strokeWidth={isOutbound || isInbound ? 1.6 : 1.15}
                strokeLinecap="round"
                initial={reduced ? false : { opacity: 0 }}
                animate={{ opacity: mutedEdgeOpacity(state, isInbound, isOutbound) }}
                transition={{ duration: 0.35 }}
              />
            )
          })}
          {layout.nodes.map((p, i) => {
            const isCenter = i === 0
            const isInbound = i === layout.inboundIndex
            const isOutbound = layout.outboundIndices.includes(i)
            const r = isCenter ? 5.5 : isInbound || isOutbound ? 3.2 : 2.6
            return (
              <motion.circle
                key={`n-${state}-${i}`}
                cx={p.x}
                cy={p.y}
                r={r}
                fill={
                  isCenter
                    ? "var(--color-brand, #16a374)"
                    : isInbound
                      ? "var(--color-blue-500)"
                      : isOutbound
                        ? "var(--color-brand, #16a374)"
                        : "color-mix(in srgb, var(--g-intelligence) 35%, #9aa3ad)"
                }
                initial={reduced ? false : { scale: 0.6, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ duration: 0.3, delay: reduced ? 0 : i * 0.02 }}
              />
            )
          })}
        </svg>

        <div className="relative z-10 flex flex-col items-center justify-center rounded-lg bg-white/90 px-2 py-1 text-[color:var(--color-brand,#16a374)] shadow-sm backdrop-blur-[1px]">
          <LogoSVG className="size-5" />
          <span className="mt-0.5 text-[7px] font-bold uppercase tracking-[0.08em] text-[color:var(--g-text-muted)]">
            Core
          </span>
        </div>
      </motion.div>

      <AnimatePresence mode="wait">
        {label ? (
          <motion.span
            key={state}
            initial={reduced ? false : { opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduced ? undefined : { opacity: 0 }}
            className="relative z-30 rounded-md border border-[color:var(--color-line,#eaedf1)] bg-white px-2.5 py-1 text-[10px] font-semibold text-[color:var(--color-brand,#16a374)] shadow-sm"
          >
            {label}
          </motion.span>
        ) : (
          <span className="h-[26px]" aria-hidden />
        )}
      </AnimatePresence>
    </div>
  )
}

function mutedEdgeOpacity(state: CoreState, inbound: boolean, outbound: boolean): number {
  if (state === "idle") return 0.55
  if (inbound || outbound) return 0.95
  if (state === "learning" || state === "learned") return 0.9
  return 0.75
}
