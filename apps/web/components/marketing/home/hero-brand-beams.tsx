"use client"

/**
 * @deprecated Design Pass 2 — superseded by IntelligenceField on the marketing hero.
 * Kept for reference / potential non-hero reuse. Prefer `@/components/gravitre/visual`.
 *
 * Aceternity-inspired beam atmosphere for the marketing hero.
 * Pattern only — retokened to Gravitre emerald / semantic surfaces.
 * Do not import Aceternity purple gradients or ship foreign brand chrome.
 */

import { motion } from "framer-motion"
import { useMotionPrefs } from "@/lib/animations"
import { cn } from "@/lib/utils"

const BEAM_PATHS = [
  "M-40 40C80 120 200 80 360 160C520 240 640 200 780 280",
  "M-20 120C100 200 220 160 380 240C540 320 660 280 800 360",
  "M0 200C120 280 240 240 400 320C560 400 680 360 820 440",
  "M20 280C140 360 260 320 420 400C580 480 700 440 840 520",
]

export function HeroBrandBeams({ className }: { className?: string }) {
  const { reduced } = useMotionPrefs()

  return (
    <div
      aria-hidden
      className={cn(
        "pointer-events-none absolute inset-0 overflow-hidden",
        className,
      )}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-primary/8 via-background to-info/5" />

      <svg
        className="absolute inset-0 h-full w-full opacity-70"
        width="100%"
        height="100%"
        viewBox="0 0 800 560"
        fill="none"
        preserveAspectRatio="xMidYMid slice"
      >
        {BEAM_PATHS.map((d, index) =>
          reduced ? (
            <path
              key={d}
              d={d}
              stroke="var(--primary)"
              strokeOpacity={0.12 + index * 0.03}
              strokeWidth={0.8}
            />
          ) : (
            <motion.path
              key={d}
              d={d}
              stroke="url(#gv-hero-beam-grad)"
              strokeOpacity={0.45}
              strokeWidth={0.9}
              initial={{ pathLength: 0.2, opacity: 0.35 }}
              animate={{ pathLength: [0.35, 1, 0.35], opacity: [0.25, 0.55, 0.25] }}
              transition={{
                duration: 10 + index * 1.5,
                repeat: Infinity,
                ease: "easeInOut",
                delay: index * 0.6,
              }}
            />
          ),
        )}
        <defs>
          <linearGradient id="gv-hero-beam-grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="var(--primary)" stopOpacity="0" />
            <stop offset="40%" stopColor="var(--primary)" stopOpacity="0.9" />
            <stop offset="100%" stopColor="var(--info)" stopOpacity="0" />
          </linearGradient>
        </defs>
      </svg>

      <div
        className="absolute inset-0 opacity-[0.035]"
        style={{
          backgroundImage: `
            linear-gradient(var(--foreground) 1px, transparent 1px),
            linear-gradient(90deg, var(--foreground) 1px, transparent 1px)
          `,
          backgroundSize: "64px 64px",
        }}
      />
    </div>
  )
}
