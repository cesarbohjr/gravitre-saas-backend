"use client"

/**
 * Departments converge — About page signature.
 */

import { motion, useReducedMotion } from "framer-motion"
import { cn } from "@/lib/utils"

const NODES = [
  { label: "Sales", x: 70, y: 70 },
  { label: "Support", x: 310, y: 70 },
  { label: "Ops", x: 70, y: 210 },
  { label: "Finance", x: 310, y: 210 },
] as const

export function ConvergeNodesVisual({ className }: { className?: string }) {
  const reduce = useReducedMotion()
  const cx = 190
  const cy = 140

  return (
    <div className={cn("relative mx-auto w-full max-w-sm", className)}>
      <svg viewBox="0 0 380 280" className="h-auto w-full" role="img" aria-label="Departments converge into one brain">
        {NODES.map((node, i) => (
          <g key={node.label}>
            <motion.line
              x1={node.x}
              y1={node.y}
              x2={cx}
              y2={cy}
              stroke="color-mix(in oklch, var(--g-intelligence) 30%, #eaedf1)"
              strokeWidth="1.25"
              strokeDasharray="4 6"
              initial={reduce ? false : { opacity: 0 }}
              whileInView={reduce ? undefined : { opacity: 1 }}
              viewport={{ once: true }}
              transition={{ delay: 0.1 * i, duration: 0.5 }}
            />
            <motion.circle
              cx={node.x}
              cy={node.y}
              r={22}
              fill="#fff"
              stroke="color-mix(in oklch, var(--g-intelligence) 40%, #eaedf1)"
              strokeWidth="1.25"
              initial={reduce ? false : { scale: 0.7, opacity: 0 }}
              whileInView={reduce ? undefined : { scale: 1, opacity: 1 }}
              viewport={{ once: true }}
              transition={{ delay: 0.08 * i, duration: 0.4 }}
            />
            <text
              x={node.x}
              y={node.y + 4}
              textAnchor="middle"
              style={{ fontSize: 10, fontWeight: 600 }}
              className="fill-[color:var(--g-text-secondary)]"
            >
              {node.label}
            </text>
          </g>
        ))}
        <motion.circle
          cx={cx}
          cy={cy}
          r={32}
          fill="#fff"
          stroke="var(--primary)"
          strokeWidth="1.75"
          initial={reduce ? false : { scale: 0.75, opacity: 0 }}
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
          One brain
        </text>
      </svg>
    </div>
  )
}
