"use client"

/**
 * Reusable horizontal TRACE path for Marketing System 4.0 P1 pages.
 * No TRAINED badges, prices, or entitlement claims.
 */

import { useEffect, useState } from "react"
import { motion, useReducedMotion } from "framer-motion"
import { cn } from "@/lib/utils"
import { NodusDotField } from "@/components/marketing/nodus/dot-field"

export type TraceStage = {
  id: string
  label: string
}

type Props = {
  stages: readonly TraceStage[]
  caption?: string
  ariaLabel: string
  className?: string
  /** Kept for callers; the trace no longer uses an SVG gradient. */
  gradientId?: string
  /** Optional item names; one rides the signal per loop as a small card. */
  payloads?: readonly string[]
}

/** One signal loop: TRAVEL is the share of the loop spent moving, the rest is the fade. */
const LOOP = 4.2
const TRAVEL = 0.78

export function StageTraceVisual({
  stages,
  caption,
  ariaLabel,
  className,
  payloads,
}: Props) {
  const reduce = useReducedMotion()
  const [payloadIndex, setPayloadIndex] = useState(0)
  useEffect(() => {
    if (reduce || !payloads?.length) return
    const id = window.setInterval(() => setPayloadIndex((i) => (i + 1) % payloads.length), LOOP * 1000)
    return () => window.clearInterval(id)
  }, [reduce, payloads])
  const count = stages.length
  const width = 880
  const y = 120
  const pad = 80
  const span = width - pad * 2
  const xs = stages.map((_, i) => (count === 1 ? width / 2 : pad + (span * i) / (count - 1)))

  return (
    <div className={cn("relative mx-auto w-full max-w-4xl", className)}>
      <NodusDotField className="-inset-x-8 -inset-y-6" />
      <svg
        viewBox={`0 0 ${width} 220`}
        className="relative h-auto w-full"
        role="img"
        aria-label={ariaLabel}
      >
        {/* Rail: always visible, so the stages read as connected even at rest. */}
        <line
          x1={xs[0]}
          y1={y}
          x2={xs[count - 1]}
          y2={y}
          stroke="var(--color-line, #e4e4df)"
          strokeWidth={2}
          strokeLinecap="round"
        />

        {/* Signal: a green trail runs stage to stage on a loop, lighting each node as it passes. */}
        {reduce ? (
          <line
            x1={xs[0]}
            y1={y}
            x2={xs[count - 1]}
            y2={y}
            stroke="var(--color-brand, #0b8a5c)"
            strokeWidth={2}
            strokeLinecap="round"
          />
        ) : (
          <>
            <motion.line
              x1={xs[0]}
              y1={y}
              y2={y}
              stroke="var(--color-brand, #0b8a5c)"
              strokeWidth={2}
              strokeLinecap="round"
              initial={{ x2: xs[0], opacity: 0 }}
              animate={{ x2: [xs[0], xs[count - 1], xs[count - 1]], opacity: [1, 1, 0] }}
              transition={{ duration: LOOP, times: [0, TRAVEL, 1], ease: "easeInOut", repeat: Infinity }}
            />
            <motion.circle
              cy={y}
              r={4}
              fill="var(--color-brand, #0b8a5c)"
              initial={{ cx: xs[0], opacity: 0 }}
              animate={{ cx: [xs[0], xs[count - 1], xs[count - 1]], opacity: [1, 1, 0] }}
              transition={{ duration: LOOP, times: [0, TRAVEL, 1], ease: "easeInOut", repeat: Infinity }}
            />
          </>
        )}

        {!reduce && payloads?.length ? (
          <motion.g
            initial={{ x: xs[0], opacity: 0 }}
            animate={{ x: [xs[0], xs[count - 1], xs[count - 1]], opacity: [1, 1, 0] }}
            transition={{ duration: LOOP, times: [0, TRAVEL, 1], ease: "easeInOut", repeat: Infinity }}
          >
            <rect
              x={-76}
              y={y - 58}
              width={152}
              height={30}
              rx={8}
              fill="var(--card)"
              stroke="var(--color-line, #e4e4df)"
              style={{ filter: "drop-shadow(0 2px 6px rgba(0,0,0,0.08))" }}
            />
            <circle cx={-62} cy={y - 43} r={3.5} fill="var(--color-brand, #0b8a5c)" />
            <text
              x={-52}
              y={y - 39}
              className="fill-[color:var(--g-text-primary,#1f2421)]"
              style={{ fontSize: 11, fontWeight: 500 }}
            >
              {payloads[payloadIndex]}
            </text>
            <line x1={0} y1={y - 28} x2={0} y2={y - 6} stroke="var(--color-line, #e4e4df)" strokeDasharray="2 3" />
          </motion.g>
        ) : null}

        {stages.map((stage, index) => {
          const at = count === 1 ? 0 : (TRAVEL * index) / (count - 1)
          const last = index === count - 1
          return (
            <g key={stage.id}>
              {reduce ? null : (
                <motion.circle
                  cx={xs[index]}
                  cy={y}
                  fill="none"
                  stroke="var(--color-brand, #0b8a5c)"
                  strokeWidth={1.5}
                  initial={{ r: 20, opacity: 0 }}
                  animate={{ r: [20, 20, 22, 30, 30], opacity: [0, 0, 0.55, 0, 0] }}
                  transition={{
                    duration: LOOP,
                    times: [0, at, Math.min(at + 0.04, 1), Math.min(at + 0.16, 1), 1],
                    repeat: Infinity,
                  }}
                />
              )}
              <motion.rect
                x={xs[index] - 17}
                y={y - 17}
                width={34}
                height={34}
                rx={9}
                fill="var(--card)"
                stroke={last ? "var(--color-brand, #0b8a5c)" : "var(--color-line, #e4e4df)"}
                strokeWidth="1.25"
                style={{
                  filter: "drop-shadow(0 1px 1px rgba(0,0,0,0.05)) drop-shadow(0 4px 10px rgba(0,0,0,0.06))",
                  transformBox: "fill-box",
                  transformOrigin: "center",
                }}
                initial={reduce ? false : { scale: 0.7, opacity: 0 }}
                whileInView={reduce ? undefined : { scale: 1, opacity: 1 }}
                viewport={{ once: true }}
                transition={{ delay: 0.12 + index * 0.1, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
              />
              {reduce || last ? (
                <circle
                  cx={xs[index]}
                  cy={y}
                  r={5}
                  fill={last ? "var(--color-brand, #0b8a5c)" : "var(--color-charcoal-700, #3f4b45)"}
                />
              ) : (
                <motion.circle
                  cx={xs[index]}
                  cy={y}
                  r={5}
                  initial={{ fill: "var(--color-charcoal-700, #3f4b45)" }}
                  animate={{
                    fill: [
                      "var(--color-charcoal-700, #3f4b45)",
                      "var(--color-charcoal-700, #3f4b45)",
                      "var(--color-brand, #0b8a5c)",
                      "var(--color-brand, #0b8a5c)",
                      "var(--color-charcoal-700, #3f4b45)",
                    ],
                  }}
                  transition={{
                    duration: LOOP,
                    times: [0, at, Math.min(at + 0.03, 1), 0.92, 1],
                    repeat: Infinity,
                  }}
                />
              )}
              <text
                x={xs[index]}
                y={y + 42}
                textAnchor="middle"
                className="fill-[color:var(--g-text-primary,#1f2421)]"
                style={{ fontSize: 12.5, fontWeight: 500 }}
              >
                {stage.label}
              </text>
              <text
                x={xs[index]}
                y={y + 58}
                textAnchor="middle"
                className="fill-gray-500 font-mono"
                style={{ fontSize: 10 }}
              >
                {String(index + 1).padStart(2, "0")}
              </text>
            </g>
          )
        })}
      </svg>
      {caption ? (
        <p className="mt-2 text-center text-sm text-gray-600">{caption}</p>
      ) : null}
    </div>
  )
}

/** Extension: overlay → approval → outcome */
export const EXTENSION_TRACE_STAGES = [
  { id: "overlay", label: "Overlay" },
  { id: "enrich", label: "Enrich" },
  { id: "approve", label: "Approve" },
  { id: "outcome", label: "Outcome" },
] as const

/** Marketplace: readiness → gate → live */
export const MARKETPLACE_TRACE_STAGES = [
  { id: "browse", label: "Browse" },
  { id: "readiness", label: "Readiness" },
  { id: "gate", label: "Approval gate" },
  { id: "live", label: "Live" },
] as const

/** Security: governance FLOW */
export const SECURITY_TRACE_STAGES = [
  { id: "identity", label: "Identity" },
  { id: "encrypt", label: "Encrypt" },
  { id: "approve", label: "Approve" },
  { id: "audit", label: "Audit" },
] as const

/** API: request → audit TRACE */
export const API_TRACE_STAGES = [
  { id: "auth", label: "Auth" },
  { id: "request", label: "Request" },
  { id: "approve", label: "Approve" },
  { id: "audit", label: "Audit" },
] as const

/** Docs: system map spine */
export const DOCS_TRACE_STAGES = [
  { id: "start", label: "Start" },
  { id: "connect", label: "Connect" },
  { id: "build", label: "Build" },
  { id: "govern", label: "Govern" },
  { id: "learn", label: "Learn" },
] as const

/** Careers: ownership timeline */
export const CAREERS_TRACE_STAGES = [
  { id: "own", label: "Own" },
  { id: "ship", label: "Ship" },
  { id: "learn", label: "Learn" },
  { id: "impact", label: "Impact" },
] as const

/** Blog: field evidence outcome */
export const BLOG_TRACE_STAGES = [
  { id: "field", label: "Field" },
  { id: "evidence", label: "Evidence" },
  { id: "outcome", label: "Outcome" },
] as const

/** Changelog: ship → measure → learn */
export const CHANGELOG_TRACE_STAGES = [
  { id: "ship", label: "Ship" },
  { id: "measure", label: "Measure" },
  { id: "learn", label: "Learn" },
] as const

/** Roadmap: site story spine (framer sticky — not GSAP) */
export const ROADMAP_TRACE_STAGES = [
  { id: "connect", label: "Connect" },
  { id: "understand", label: "Understand" },
  { id: "coordinate", label: "Coordinate" },
  { id: "act", label: "Act" },
  { id: "verify", label: "Verify" },
  { id: "learn", label: "Learn" },
] as const

/** Guides: learning path FLOW */
export const GUIDES_TRACE_STAGES = [
  { id: "setup", label: "Setup" },
  { id: "agent", label: "Agent" },
  { id: "connect", label: "Connect" },
  { id: "workflow", label: "Workflow" },
  { id: "optimize", label: "Optimize" },
] as const

/** Support: calm escalation */
export const SUPPORT_TRACE_STAGES = [
  { id: "find", label: "Find" },
  { id: "guide", label: "Guide" },
  { id: "escalate", label: "Escalate" },
  { id: "resolve", label: "Resolve" },
] as const

/** Pricing: plan → role → outcome (prices stay PLAN_CATALOG-only) */
export const PRICING_TRACE_STAGES = [
  { id: "plan", label: "Plan" },
  { id: "role", label: "Role" },
  { id: "outcome", label: "Outcome" },
] as const

/** Features: agents coordinate → resolve (not a home clone) */
export const FEATURES_TRACE_STAGES = [
  { id: "coordinate", label: "Coordinate" },
  { id: "act", label: "Act" },
  { id: "approve", label: "Approve" },
  { id: "resolve", label: "Resolve" },
] as const
