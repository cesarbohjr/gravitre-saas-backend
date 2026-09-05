"use client"

/**
 * Aceternity-inspired background lines for marketing sections (marketing only).
 * Retokened to Gravitre primary/info — not Aceternity purple.
 */

import { motion } from "framer-motion"
import { useMotionPrefs } from "@/lib/animations"
import { cn } from "@/lib/utils"

const LINES = 12

export function MarketingBackgroundLines({ className }: { className?: string }) {
  const { reduced } = useMotionPrefs()

  return (
    <div aria-hidden className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}>
      <svg className="absolute inset-0 h-full w-full opacity-[0.09]" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="gv-mkt-line-grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="var(--primary)" stopOpacity="0" />
            <stop offset="45%" stopColor="var(--primary)" stopOpacity="1" />
            <stop offset="100%" stopColor="var(--info)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {Array.from({ length: LINES }).map((_, i) => {
          const x1 = `${4 + i * 8}%`
          const x2 = `${18 + i * 7}%`
          if (reduced) {
            return (
              <line
                key={i}
                x1={x1}
                y1="0%"
                x2={x2}
                y2="100%"
                stroke="var(--primary)"
                strokeOpacity={0.2}
                strokeWidth="1"
              />
            )
          }
          return (
            <motion.line
              key={i}
              x1={x1}
              y1="0%"
              x2={x2}
              y2="100%"
              stroke="url(#gv-mkt-line-grad)"
              strokeWidth="1"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: [0, 0.55, 0] }}
              transition={{
                duration: 5.5,
                delay: i * 0.35,
                repeat: Infinity,
                ease: "easeInOut",
              }}
            />
          )
        })}
      </svg>
    </div>
  )
}
