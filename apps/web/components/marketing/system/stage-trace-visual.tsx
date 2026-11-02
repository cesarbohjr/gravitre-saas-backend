"use client"

/**
 * Reusable horizontal TRACE path for Marketing System 4.0 P1 pages.
 * No TRAINED badges, prices, or entitlement claims.
 */

import { useEffect, useId, useState } from "react"
import { motion } from "framer-motion"
import { useReducedMotion } from "@/lib/use-reduced-motion"
import { cn } from "@/lib/utils"
import { NodusDotField } from "@/components/marketing/nodus/dot-field"
import { NodusBeam } from "@/components/marketing/nodus/scenes/kit"

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
  const gid = `trace-${useId().replace(/:/g, "")}`
  const count = stages.length
  const width = 880
  const y = 120
  const pad = 80
  const span = width - pad * 2
  const xs = stages.map((_, i) => (count === 1 ? width / 2 : pad + (span * i) / (count - 1)))

  return (
    <div className={cn("@container relative mx-auto w-full max-w-4xl", className)}>
      <NodusDotField className="-inset-x-8 -inset-y-6" />
      <VerticalTrace stages={stages} ariaLabel={ariaLabel} />
      <svg
        viewBox={`0 0 ${width} 220`}
        className="relative hidden h-auto w-full @min-[620px]:block"
        role="img"
        aria-label={ariaLabel}
      >
        {/* Nodus rail: a hairline with the Nodus travelling pulse (same as the
            home skeleton connectors). Ambient, so it keeps running under
            Reduce Motion by Cesar's call (2026-11-02). */}
        <line x1={xs[0]} y1={y} x2={xs[count - 1]} y2={y} stroke="var(--color-line, #e4e4df)" strokeLinecap="round" />
        <line x1={xs[0]} y1={y} x2={xs[count - 1]} y2={y} stroke={`url(#${gid})`} strokeLinecap="round" />
        <defs>
          <motion.linearGradient
            id={gid}
            gradientUnits="userSpaceOnUse"
            initial={{ x1: xs[0] - 160, x2: xs[0], y1: y, y2: y }}
            animate={{ x1: xs[count - 1], x2: xs[count - 1] + 160, y1: y, y2: y }}
            transition={{ duration: LOOP * TRAVEL, repeat: Infinity, repeatType: "loop", ease: "easeInOut", repeatDelay: LOOP * (1 - TRAVEL) }}
          >
            <stop stopColor="var(--color-line, #e4e4df)" />
            <stop offset="0.33" stopColor="var(--brand)" />
            <stop offset="0.66" stopColor="var(--brand)" />
            <stop offset="1" stopColor="var(--color-line, #e4e4df)" />
          </motion.linearGradient>
        </defs>

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
          const last = index === count - 1
          return (
            <g key={stage.id}>
              <motion.rect
                x={xs[index] - 20}
                y={y - 20}
                width={40}
                height={40}
                rx={6}
                fill={last ? "color-mix(in srgb, var(--brand) 6%, var(--card))" : "var(--card)"}
                stroke={last ? "color-mix(in srgb, var(--brand) 25%, transparent)" : "var(--border)"}
                strokeWidth="1"
                style={{
                  filter: "drop-shadow(0 1px 1px rgba(0,0,0,0.05)) drop-shadow(0 4px 10px rgba(0,0,0,0.06))",
                  transformBox: "fill-box",
                  transformOrigin: "center",
                }}
                initial={reduce ? false : { scale: 0.7, opacity: 0 }}
                whileInView={{ scale: 1, opacity: 1 }}
                viewport={{ once: true }}
                transition={{ delay: 0.12 + index * 0.1, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
              />
              <circle
                cx={xs[index]}
                cy={y}
                r={4}
                fill={last ? "var(--color-brand, #0b8a5c)" : "var(--color-gray-400, #cbcbc3)"}
              />
              <text
                x={xs[index]}
                y={y + 46}
                textAnchor="middle"
                className="fill-[color:var(--g-text-primary,#1f2421)]"
                style={{ fontSize: 12.5, fontWeight: 500 }}
              >
                {stage.label}
              </text>
              <text
                x={xs[index]}
                y={y + 62}
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

/**
 * Phone layout: the same trace stacked top to bottom, so the 40px Nodus tiles
 * and labels stay full size instead of shrinking with the 880px-wide SVG.
 */
const ROW = 64
const TILE = 40

function VerticalTrace({ stages, ariaLabel }: { stages: readonly TraceStage[]; ariaLabel: string }) {
  const count = stages.length
  const rail = ROW * (count - 1)
  return (
    <div role="img" aria-label={ariaLabel} className="relative mx-auto w-fit py-2 @min-[620px]:hidden">
      {count > 1 ? (
        <NodusBeam
          d={`M0.5,0.5 L0.5,${rail + 0.5}`}
          width={2}
          height={rail + 1}
          axis="y"
          tone="brand"
          duration={LOOP * TRAVEL}
          style={{ left: TILE / 2 - 0.5, top: 8 + TILE / 2 }}
        />
      ) : null}
      <ol className="relative flex flex-col" style={{ gap: ROW - TILE }}>
        {stages.map((stage, index) => {
          const last = index === count - 1
          return (
            <li key={stage.id} className="flex items-center gap-4">
              <span
                className={cn(
                  "flex shrink-0 items-center justify-center rounded-md border shadow-md",
                  last ? "border-brand/25 bg-[color:color-mix(in_srgb,var(--brand)_6%,var(--card))]" : "border-border bg-card",
                )}
                style={{ width: TILE, height: TILE }}
              >
                <span className={cn("size-2 rounded-full", last ? "bg-brand" : "bg-gray-400")} />
              </span>
              <span className="flex min-w-24 items-baseline gap-3">
                <span className="text-charcoal-700 text-sm font-medium">{stage.label}</span>
                <span className="font-mono text-xs text-gray-500">{String(index + 1).padStart(2, "0")}</span>
              </span>
            </li>
          )
        })}
      </ol>
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
