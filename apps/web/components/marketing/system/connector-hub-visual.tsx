"use client"

/**
 * Connector hub motif — spokes into one governed center.
 * Used on docs/integrations (and optionally docs hub).
 */

import { motion, useReducedMotion } from "framer-motion"
import { cn } from "@/lib/utils"

const SPOKES = [
  { label: "CRM", angle: -90 },
  { label: "Support", angle: -30 },
  { label: "Comms", angle: 30 },
  { label: "Dev", angle: 90 },
  { label: "Finance", angle: 150 },
  { label: "Ops", angle: 210 },
] as const

export function ConnectorHubVisual({ className }: { className?: string }) {
  const reduce = useReducedMotion()
  const cx = 200
  const cy = 160
  const r = 92

  return (
    <div className={cn("relative mx-auto w-full max-w-md", className)}>
      <svg viewBox="0 0 400 320" className="h-auto w-full" role="img" aria-label="Connectors converge into Gravitre">
        <defs>
          <radialGradient id="hub-glow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="color-mix(in oklch, var(--g-intelligence) 18%, transparent)" />
            <stop offset="100%" stopColor="transparent" />
          </radialGradient>
        </defs>
        <circle cx={cx} cy={cy} r={130} fill="url(#hub-glow)" />
        {SPOKES.map((spoke, i) => {
          const rad = (spoke.angle * Math.PI) / 180
          const x = cx + Math.cos(rad) * r
          const y = cy + Math.sin(rad) * r
          return (
            <g key={spoke.label}>
              <motion.line
                x1={cx}
                y1={cy}
                x2={x}
                y2={y}
                stroke="color-mix(in oklch, var(--g-intelligence) 35%, #eaedf1)"
                strokeWidth="1.25"
                initial={reduce ? false : { opacity: 0 }}
                whileInView={reduce ? undefined : { opacity: 1 }}
                viewport={{ once: true }}
                transition={{ delay: 0.08 * i, duration: 0.55 }}
              />
              <motion.circle
                cx={x}
                cy={y}
                r={18}
                fill="#fff"
                stroke="color-mix(in oklch, var(--g-intelligence) 40%, #eaedf1)"
                strokeWidth="1.25"
                initial={reduce ? false : { scale: 0.6, opacity: 0 }}
                whileInView={reduce ? undefined : { scale: 1, opacity: 1 }}
                viewport={{ once: true }}
                transition={{ delay: 0.1 + 0.08 * i, duration: 0.4 }}
              />
              <text
                x={x}
                y={y + 4}
                textAnchor="middle"
                style={{ fontSize: 9, fontWeight: 600 }}
                className="fill-[color:var(--g-text-secondary)]"
              >
                {spoke.label}
              </text>
            </g>
          )
        })}
        <motion.circle
          cx={cx}
          cy={cy}
          r={28}
          fill="#fff"
          stroke="var(--primary)"
          strokeWidth="1.75"
          initial={reduce ? false : { scale: 0.8, opacity: 0 }}
          whileInView={reduce ? undefined : { scale: 1, opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.35, duration: 0.45 }}
        />
        <text
          x={cx}
          y={cy + 4}
          textAnchor="middle"
          style={{ fontSize: 11, fontWeight: 700 }}
          className="fill-[color:var(--primary)]"
        >
          Gravitre
        </text>
      </svg>
      <p className="mt-1 text-center text-sm text-gray-600">
        Brand connectors feed one governed hub — setup guides only, not entitlement claims.
      </p>
    </div>
  )
}
