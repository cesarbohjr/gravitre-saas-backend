"use client"

import { motion, useReducedMotion } from "framer-motion"
import { Target, Bot, Layers } from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * Teaches the swarm mental model in one glance:
 *   one objective  ->  fans out to parallel agents  ->  converges to a council result
 *
 * Used for both the empty state (variant="hero") and the idle right panel
 * (variant="panel"). Pure presentational SVG + tokens; respects reduced motion.
 */

type Variant = "hero" | "panel"

export function SwarmConvergenceDiagram({
  variant = "hero",
  className,
}: {
  variant?: Variant
  className?: string
}) {
  const reduced = useReducedMotion()
  const compact = variant === "panel"

  // Three parallel agent lanes between the source objective and the aggregate.
  const laneYs = compact ? [22, 50, 78] : [26, 60, 94]
  const W = 280
  const H = compact ? 100 : 120
  const xSource = 30
  const xAgents = W / 2
  const xResult = W - 30

  const dash = reduced ? undefined : { strokeDasharray: "4 5" }

  return (
    <div className={cn("mx-auto w-full max-w-[320px]", className)}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label="A single objective fans out to parallel agents, then converges into one aggregated result."
      >
        {/* Connector paths: source -> each agent -> result */}
        {laneYs.map((y, i) => (
          <g key={i} className="text-border">
            <path
              d={`M${xSource + 14},${H / 2} C${(xSource + xAgents) / 2},${H / 2} ${(xSource + xAgents) / 2},${y} ${xAgents - 16},${y}`}
              stroke="currentColor"
              strokeWidth={1.5}
              fill="none"
              {...dash}
            />
            <path
              d={`M${xAgents + 16},${y} C${(xAgents + xResult) / 2},${y} ${(xAgents + xResult) / 2},${H / 2} ${xResult - 14},${H / 2}`}
              stroke="currentColor"
              strokeWidth={1.5}
              fill="none"
              {...dash}
            />
            {!reduced && (
              <motion.circle
                r={2.5}
                className="text-primary"
                fill="currentColor"
                initial={{ opacity: 0 }}
                animate={{ opacity: [0, 1, 1, 0] }}
                transition={{ duration: 2.4, repeat: Infinity, delay: i * 0.4, ease: "easeInOut" }}
              >
                <animateMotion
                  dur="2.4s"
                  repeatCount="indefinite"
                  begin={`${i * 0.4}s`}
                  path={`M${xSource + 14},${H / 2} C${(xSource + xAgents) / 2},${H / 2} ${(xSource + xAgents) / 2},${y} ${xAgents},${y} C${(xAgents + xResult) / 2},${y} ${(xAgents + xResult) / 2},${H / 2} ${xResult - 14},${H / 2}`}
                />
              </motion.circle>
            )}
          </g>
        ))}

        {/* Source objective node */}
        <g>
          <circle cx={xSource} cy={H / 2} r={13} className="fill-primary/10 stroke-primary" strokeWidth={1.5} />
          <foreignObject x={xSource - 8} y={H / 2 - 8} width={16} height={16}>
            <Target className="h-4 w-4 text-primary" />
          </foreignObject>
        </g>

        {/* Parallel agent nodes */}
        {laneYs.map((y, i) => (
          <g key={`a-${i}`}>
            <circle cx={xAgents} cy={y} r={12} className="fill-info/10 stroke-info" strokeWidth={1.5} />
            <foreignObject x={xAgents - 7} y={y - 7} width={14} height={14}>
              <Bot className="h-3.5 w-3.5 text-info" />
            </foreignObject>
          </g>
        ))}

        {/* Aggregate / council result node */}
        <g>
          <circle cx={xResult} cy={H / 2} r={13} className="fill-success/10 stroke-success" strokeWidth={1.5} />
          <foreignObject x={xResult - 8} y={H / 2 - 8} width={16} height={16}>
            <Layers className="h-4 w-4 text-success" />
          </foreignObject>
        </g>
      </svg>

      {!compact && (
        <div className="mt-3 flex items-center justify-between px-1 text-[10px] font-medium uppercase tracking-wide">
          <span className="text-primary">Objective</span>
          <span className="text-info">Parallel agents</span>
          <span className="text-success">Aggregate</span>
        </div>
      )}
    </div>
  )
}
