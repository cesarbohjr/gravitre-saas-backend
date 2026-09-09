"use client"

/**
 * Soft signal field — Contact page ambient (calm, not a second hero).
 */

import { motion, useReducedMotion } from "framer-motion"
import { cn } from "@/lib/utils"

export function SignalFieldVisual({ className }: { className?: string }) {
  const reduce = useReducedMotion()

  return (
    <div className={cn("relative mx-auto w-full max-w-xs", className)} aria-hidden>
      <svg viewBox="0 0 280 200" className="h-auto w-full">
        {[48, 78, 108].map((r, i) => (
          <motion.circle
            key={r}
            cx={140}
            cy={100}
            r={r}
            fill="none"
            stroke="color-mix(in oklch, var(--g-intelligence) 28%, transparent)"
            strokeWidth="1"
            initial={reduce ? false : { opacity: 0, scale: 0.85 }}
            animate={
              reduce
                ? undefined
                : {
                    opacity: [0.25, 0.55, 0.25],
                    scale: [0.96, 1, 0.96],
                  }
            }
            transition={
              reduce
                ? undefined
                : {
                    delay: i * 0.35,
                    duration: 5.5,
                    repeat: Number.POSITIVE_INFINITY,
                    ease: "easeInOut",
                  }
            }
          />
        ))}
        <circle cx={140} cy={100} r={10} fill="var(--primary)" opacity={0.85} />
        <circle cx={140} cy={100} r={4} fill="#fff" />
      </svg>
    </div>
  )
}
