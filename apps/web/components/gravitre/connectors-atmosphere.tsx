"use client"

/**
 * Connectors canvas atmosphere — same animated-line language as the marketing
 * homepage background lines (Aceternity-inspired, Gravitre-retokened).
 * Dot grid + soft horizontal streaks match the Nodus/agent network visual.
 */

import { motion } from "framer-motion"
import { useMotionPrefs } from "@/lib/animations"
import { cn } from "@/lib/utils"

const DIAGONAL_LINES = 10
const HORIZONTAL_STREAKS = [
  { y: "18%", delay: 0 },
  { y: "34%", delay: 1.1 },
  { y: "52%", delay: 0.4 },
  { y: "68%", delay: 1.8 },
  { y: "82%", delay: 0.9 },
]

export function ConnectorsAtmosphere({ className }: { className?: string }) {
  const { reduced } = useMotionPrefs()

  return (
    <div
      aria-hidden
      className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}
      data-connectors-atmosphere=""
    >
      {/* Dot grid — same mineral language as marketing daylight fields */}
      <div
        className="absolute inset-0 opacity-[0.4]"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, color-mix(in oklch, var(--g-text-primary) 10%, transparent) 1px, transparent 0)",
          backgroundSize: "28px 28px",
          maskImage: "radial-gradient(ellipse 85% 75% at 50% 40%, black 15%, transparent 78%)",
        }}
      />

      {/* Soft brand washes */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 50% 40% at 20% 30%, color-mix(in oklch, var(--g-emerald) 8%, transparent), transparent 70%), radial-gradient(ellipse 45% 35% at 78% 55%, color-mix(in oklch, var(--g-intelligence) 7%, transparent), transparent 68%), radial-gradient(ellipse 40% 30% at 55% 80%, color-mix(in oklch, var(--g-signal) 6%, transparent), transparent 65%)",
        }}
      />

      <svg className="absolute inset-0 h-full w-full" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="gv-conn-diag-grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="var(--g-emerald)" stopOpacity="0" />
            <stop offset="40%" stopColor="var(--g-intelligence)" stopOpacity="0.85" />
            <stop offset="100%" stopColor="var(--g-signal)" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="gv-conn-h-grad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="var(--g-emerald)" stopOpacity="0" />
            <stop offset="25%" stopColor="var(--g-signal)" stopOpacity="0.7" />
            <stop offset="50%" stopColor="var(--g-intelligence)" stopOpacity="0.9" />
            <stop offset="75%" stopColor="color-mix(in oklch, var(--g-approval) 80%, var(--g-emerald))" stopOpacity="0.55" />
            <stop offset="100%" stopColor="var(--g-emerald)" stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Diagonal brand lines — homepage MarketingBackgroundLines pattern */}
        {Array.from({ length: DIAGONAL_LINES }).map((_, i) => {
          const x1 = `${6 + i * 9}%`
          const x2 = `${20 + i * 8}%`
          if (reduced) {
            return (
              <line
                key={`d-${i}`}
                x1={x1}
                y1="0%"
                x2={x2}
                y2="100%"
                stroke="var(--g-intelligence)"
                strokeOpacity={0.12}
                strokeWidth="1"
              />
            )
          }
          return (
            <motion.line
              key={`d-${i}`}
              x1={x1}
              y1="0%"
              x2={x2}
              y2="100%"
              stroke="url(#gv-conn-diag-grad)"
              strokeWidth="1"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: [0, 0.45, 0] }}
              transition={{
                duration: 5.5,
                delay: i * 0.35,
                repeat: Infinity,
                ease: "easeInOut",
              }}
            />
          )
        })}

        {/* Horizontal chromatic streaks — Nodus agent-network atmosphere */}
        {HORIZONTAL_STREAKS.map((streak, i) =>
          reduced ? (
            <line
              key={`h-${i}`}
              x1="5%"
              y1={streak.y}
              x2="95%"
              y2={streak.y}
              stroke="var(--g-signal)"
              strokeOpacity={0.1}
              strokeWidth="1.25"
            />
          ) : (
            <motion.line
              key={`h-${i}`}
              x1="5%"
              y1={streak.y}
              x2="95%"
              y2={streak.y}
              stroke="url(#gv-conn-h-grad)"
              strokeWidth="1.35"
              strokeLinecap="round"
              initial={{ pathLength: 0.15, opacity: 0.2 }}
              animate={{ pathLength: [0.25, 1, 0.25], opacity: [0.15, 0.55, 0.15] }}
              transition={{
                duration: 9 + i * 1.2,
                delay: streak.delay,
                repeat: Infinity,
                ease: "easeInOut",
              }}
            />
          ),
        )}
      </svg>
    </div>
  )
}
