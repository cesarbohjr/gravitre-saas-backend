"use client"

/**
 * GIBE TRACE signature — knowledge → relationships → evidence → confidence → outcome.
 * Custom SVG illustration language for /features/technology (Marketing System 4.0 pilot).
 * No TRAINED badges, prices, or entitlement claims.
 */

import { motion, useReducedMotion } from "framer-motion"
import { cn } from "@/lib/utils"

const STAGES = [
  { id: "knowledge", label: "Knowledge", x: 80 },
  { id: "relationships", label: "Relationships", x: 260 },
  { id: "evidence", label: "Evidence", x: 440 },
  { id: "confidence", label: "Confidence", x: 620 },
  { id: "outcome", label: "Outcome", x: 800 },
] as const

export function GibeTraceVisual({ className }: { className?: string }) {
  const reduce = useReducedMotion()
  const y = 120

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
        viewBox="0 0 880 220"
        className="relative h-auto w-full"
        role="img"
        aria-label="GIBE intelligence path from knowledge through relationships, evidence, and confidence to outcomes"
      >
        <defs>
          <linearGradient id="gibe-trace-stroke" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="color-mix(in srgb, var(--primary) 40%, #eaedf1)" />
            <stop offset="55%" stopColor="color-mix(in oklch, var(--g-intelligence) 55%, #eaedf1)" />
            <stop offset="100%" stopColor="var(--primary)" />
          </linearGradient>
        </defs>

        {/* Trace path */}
        <motion.path
          d={`M ${STAGES[0].x} ${y} L ${STAGES[4].x} ${y}`}
          stroke="url(#gibe-trace-stroke)"
          strokeWidth="var(--g-graphic-line)"
          strokeLinecap="round"
          fill="none"
          initial={reduce ? false : { pathLength: 0, opacity: 0.35 }}
          whileInView={reduce ? undefined : { pathLength: 1, opacity: 1 }}
          viewport={{ once: true, amount: 0.4 }}
          transition={{ duration: 1.4, ease: [0.16, 1, 0.3, 1] }}
        />

        {/* Soft secondary arcs */}
        <path
          d={`M ${STAGES[0].x} ${y} Q ${STAGES[1].x} ${y - 48} ${STAGES[2].x} ${y} T ${STAGES[4].x} ${y}`}
          stroke="color-mix(in oklch, var(--g-intelligence) 25%, transparent)"
          strokeWidth="1"
          fill="none"
          strokeDasharray="3 8"
        />

        {STAGES.map((stage, index) => (
          <g key={stage.id}>
            <motion.circle
              cx={stage.x}
              cy={y}
              r={14}
              fill="#ffffff"
              stroke={
                index === STAGES.length - 1
                  ? "var(--primary)"
                  : "color-mix(in oklch, var(--g-intelligence) 45%, #eaedf1)"
              }
              strokeWidth="1.5"
              initial={reduce ? false : { scale: 0.7, opacity: 0 }}
              whileInView={reduce ? undefined : { scale: 1, opacity: 1 }}
              viewport={{ once: true }}
              transition={{ delay: 0.15 + index * 0.12, duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
            />
            <motion.circle
              cx={stage.x}
              cy={y}
              r={5}
              fill={index === STAGES.length - 1 ? "var(--primary)" : "var(--g-intelligence)"}
              initial={reduce ? false : { opacity: 0 }}
              whileInView={
                reduce
                  ? undefined
                  : {
                      opacity: [0.45, 1, 0.45],
                    }
              }
              viewport={{ once: false, amount: 0.2 }}
              transition={
                reduce
                  ? undefined
                  : {
                      delay: 0.5 + index * 0.1,
                      duration: 2.8,
                      repeat: Number.POSITIVE_INFINITY,
                      ease: "easeInOut",
                    }
              }
            />
            <text
              x={stage.x}
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
      <p className="mt-2 text-center text-sm text-gray-600">
        How GIBE moves from org knowledge to a governed business outcome — counts and paths only,
        not a silent trained claim.
      </p>
    </div>
  )
}
