"use client"

/**
 * Reusable horizontal TRACE path for Marketing System 4.0 P1 pages.
 * No TRAINED badges, prices, or entitlement claims.
 */

import { motion, useReducedMotion } from "framer-motion"
import { cn } from "@/lib/utils"

export type TraceStage = {
  id: string
  label: string
}

type Props = {
  stages: readonly TraceStage[]
  caption?: string
  ariaLabel: string
  className?: string
  gradientId?: string
}

export function StageTraceVisual({
  stages,
  caption,
  ariaLabel,
  className,
  gradientId = "stage-trace-stroke",
}: Props) {
  const reduce = useReducedMotion()
  const count = stages.length
  const width = 880
  const y = 120
  const pad = 80
  const span = width - pad * 2
  const xs = stages.map((_, i) => (count === 1 ? width / 2 : pad + (span * i) / (count - 1)))

  return (
    <div className={cn("relative mx-auto w-full max-w-4xl", className)}>
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-[var(--g-marketing-radius)]"
        style={{
          background:
            "radial-gradient(ellipse at 50% 40%, color-mix(in oklch, var(--g-intelligence) 8%, transparent), transparent 65%)",
        }}
      />
      <svg
        viewBox={`0 0 ${width} 220`}
        className="relative h-auto w-full"
        role="img"
        aria-label={ariaLabel}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="color-mix(in srgb, var(--primary) 40%, #eaedf1)" />
            <stop offset="55%" stopColor="color-mix(in oklch, var(--g-intelligence) 55%, #eaedf1)" />
            <stop offset="100%" stopColor="var(--primary)" />
          </linearGradient>
        </defs>

        <motion.path
          d={`M ${xs[0]} ${y} L ${xs[count - 1]} ${y}`}
          stroke={`url(#${gradientId})`}
          strokeWidth="var(--g-graphic-line)"
          strokeLinecap="round"
          fill="none"
          initial={reduce ? false : { pathLength: 0, opacity: 0.35 }}
          whileInView={reduce ? undefined : { pathLength: 1, opacity: 1 }}
          viewport={{ once: true, amount: 0.4 }}
          transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
        />

        {stages.map((stage, index) => (
          <g key={stage.id}>
            <motion.circle
              cx={xs[index]}
              cy={y}
              r={14}
              fill="#ffffff"
              stroke={
                index === count - 1
                  ? "var(--primary)"
                  : "color-mix(in oklch, var(--g-intelligence) 45%, #eaedf1)"
              }
              strokeWidth="1.5"
              initial={reduce ? false : { scale: 0.7, opacity: 0 }}
              whileInView={reduce ? undefined : { scale: 1, opacity: 1 }}
              viewport={{ once: true }}
              transition={{ delay: 0.12 + index * 0.1, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            />
            <circle
              cx={xs[index]}
              cy={y}
              r={5}
              fill={index === count - 1 ? "var(--primary)" : "var(--g-intelligence)"}
            />
            <text
              x={xs[index]}
              y={y + 42}
              textAnchor="middle"
              className="fill-[color:var(--g-text-secondary)]"
              style={{ fontSize: 12, fontWeight: 500 }}
            >
              {stage.label}
            </text>
          </g>
        ))}
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
