"use client"

/**
 * Calm footer closing field — slow TRACE motif, Nodus mineral restraint.
 * Decorative only; reduced-motion freezes to static final state.
 */

import { motion, useReducedMotion } from "framer-motion"
import { cn } from "@/lib/utils"

export function FooterClosingField({ className }: { className?: string }) {
  const reduce = useReducedMotion()

  return (
    <div
      aria-hidden
      className={cn(
        "pointer-events-none absolute inset-x-0 bottom-0 top-0 overflow-hidden",
        className,
      )}
    >
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 70% 55% at 50% 120%, color-mix(in srgb, var(--primary) 10%, transparent), transparent 70%)",
        }}
      />
      <svg
        className="absolute inset-x-0 bottom-0 mx-auto h-40 w-full max-w-5xl opacity-[var(--g-graphic-opacity)]"
        viewBox="0 0 960 160"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M40 110 C160 40, 280 150, 400 90 S640 30, 800 100 S900 140, 920 120"
          stroke="var(--divide)"
          strokeWidth="var(--g-graphic-line)"
          strokeLinecap="round"
        />
        <path
          d="M80 130 C200 70, 320 140, 440 100 S680 60, 840 120"
          stroke="color-mix(in srgb, var(--primary) 35%, var(--divide))"
          strokeWidth="var(--g-graphic-line)"
          strokeLinecap="round"
          strokeDasharray="4 10"
        />
        {(
          [
            [120, 88],
            [280, 118],
            [440, 72],
            [600, 104],
            [760, 86],
            [880, 112],
          ] as const
        ).map(([cx, cy], i) => (
          <motion.circle
            key={`${cx}-${cy}`}
            cx={cx}
            cy={cy}
            r={5}
            fill="color-mix(in srgb, var(--primary) 55%, white)"
            initial={false}
            animate={
              reduce
                ? undefined
                : {
                    opacity: [0.35, 0.9, 0.35],
                  }
            }
            transition={
              reduce
                ? undefined
                : {
                    duration: 4.5 + i * 0.35,
                    repeat: Number.POSITIVE_INFINITY,
                    ease: "easeInOut",
                    delay: i * 0.4,
                  }
            }
          />
        ))}
      </svg>
    </div>
  )
}
