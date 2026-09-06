"use client"

/**
 * Focal lighting for marketing product regions (Aceternity Spotlight principle,
 * retokened to Gravitre intelligence / emerald). CSS-only — no Pro source.
 */

import { motion, useMotionTemplate, useMotionValue } from "framer-motion"
import { useEffect } from "react"
import { useMotionPrefs } from "@/lib/animations"
import { cn } from "@/lib/utils"

type MarketingSpotlightProps = {
  className?: string
  /** intelligence = violet · operational = emerald · balanced = both */
  tone?: "intelligence" | "operational" | "balanced"
  /** Follow pointer on desktop when true */
  interactive?: boolean
}

export function MarketingSpotlight({
  className,
  tone = "intelligence",
  interactive = false,
}: MarketingSpotlightProps) {
  const { reduced } = useMotionPrefs()
  const mx = useMotionValue(50)
  const my = useMotionValue(35)
  const background = useMotionTemplate`radial-gradient(520px circle at ${mx}% ${my}%, var(--spot-a) 0%, transparent 62%)`

  useEffect(() => {
    if (reduced || !interactive) return
    const onMove = (e: PointerEvent) => {
      mx.set((e.clientX / window.innerWidth) * 100)
      my.set((e.clientY / window.innerHeight) * 100)
    }
    window.addEventListener("pointermove", onMove, { passive: true })
    return () => window.removeEventListener("pointermove", onMove)
  }, [reduced, interactive, mx, my])

  const spotA =
    tone === "operational"
      ? "color-mix(in oklch, var(--g-emerald) 22%, transparent)"
      : tone === "balanced"
        ? "color-mix(in oklch, var(--g-intelligence) 18%, transparent)"
        : "color-mix(in oklch, var(--g-intelligence) 24%, transparent)"

  return (
    <div
      aria-hidden
      className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}
      style={
        {
          "--spot-a": spotA,
        } as React.CSSProperties
      }
    >
      {reduced ? (
        <div
          className="absolute inset-0"
          style={{
            background: `radial-gradient(480px circle at 50% 30%, ${spotA} 0%, transparent 65%)`,
          }}
        />
      ) : (
        <motion.div className="absolute inset-0" style={{ background }} />
      )}
      {tone === "balanced" ? (
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(420px circle at 72% 68%, color-mix(in oklch, var(--g-emerald) 8%, transparent) 0%, transparent 60%)",
          }}
        />
      ) : null}
    </div>
  )
}
