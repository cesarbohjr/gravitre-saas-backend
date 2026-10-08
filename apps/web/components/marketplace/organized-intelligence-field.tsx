"use client"

import { motion, useReducedMotion } from "framer-motion"
import { cn } from "@/lib/utils"

const nodes = [
  { x: 54, y: 84, label: "Systems", tone: "muted" },
  { x: 164, y: 48, label: "Data", tone: "blue" },
  { x: 278, y: 92, label: "Agents", tone: "emerald" },
  { x: 164, y: 154, label: "Outcome", tone: "emerald" },
] as const

const paths = [
  "M54 84 C92 84 112 48 164 48",
  "M164 48 C220 48 226 92 278 92",
  "M54 84 C98 100 118 154 164 154",
  "M278 92 C238 108 220 154 164 154",
] as const

export function OrganizedIntelligenceField({ className }: { className?: string }) {
  const reduced = useReducedMotion()
  return (
    <div className={cn("relative overflow-hidden rounded-[12px] border border-[color:var(--g-bone)]/10 bg-[color:var(--g-carbon)]", className)} aria-hidden>
      <div className="absolute inset-0 opacity-40 [background-image:radial-gradient(color-mix(in_srgb,var(--g-emerald-mint)_22%,transparent)_1px,transparent_1px)] [background-size:18px_18px]" />
      <svg viewBox="0 0 332 202" className="relative h-full w-full" role="presentation">
        {paths.map((d, i) => (
          <g key={d}>
            <path d={d} fill="none" stroke="color-mix(in srgb, var(--g-emerald-mint) 16%, transparent)" strokeWidth="1.25" />
            <motion.path
              d={d}
              fill="none"
              stroke="var(--g-emerald)"
              strokeWidth="1.75"
              strokeLinecap="round"
              initial={reduced ? false : { pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: .9 }}
              transition={reduced ? { duration: 0 } : { duration: .7, delay: i * .1, ease: "easeOut" }}
            />
          </g>
        ))}
        {nodes.map((node, i) => (
          <motion.g
            key={node.label}
            initial={reduced ? false : { opacity: 0, scale: .92 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={reduced ? { duration: 0 } : { duration: .28, delay: .22 + i * .08 }}
            style={{ transformOrigin: `${node.x}px ${node.y}px` }}
          >
            <circle cx={node.x} cy={node.y} r="15" fill="var(--g-carbon)" stroke={node.tone === "blue" ? "var(--g-electric)" : node.tone === "emerald" ? "var(--g-emerald)" : "color-mix(in srgb, var(--g-emerald-mint) 45%, transparent)"} strokeWidth="1.5" />
            <circle cx={node.x} cy={node.y} r="3.5" fill={node.tone === "blue" ? "var(--g-electric)" : "var(--g-emerald)"} />
            <text x={node.x} y={node.y + 27} textAnchor="middle" fill="color-mix(in srgb, var(--g-bone) 72%, transparent)" fontSize="9" fontWeight="600">{node.label}</text>
          </motion.g>
        ))}
      </svg>
      <div className="absolute bottom-3 left-3 rounded-full border border-[color:var(--g-bone)]/10 bg-[color:var(--g-carbon)]/20 px-2 py-1 text-[9px] font-semibold text-[color:var(--g-bone)]/65 backdrop-blur-sm">
        Fragmented → coordinated
      </div>
    </div>
  )
}
