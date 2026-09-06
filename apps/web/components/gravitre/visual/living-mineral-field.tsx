"use client"

/**
 * LivingMineralField — UI 3.0 unique daylight motion atmosphere.
 * Soft drifting mineral washes + Intent→Tool→Approval→Verified trace.
 * Not IntelligenceField (dark grid). Not decorative noise.
 */

import { motion } from "framer-motion"
import { useMotionPrefs } from "@/lib/animations"
import { cn } from "@/lib/utils"
import { TracePath } from "./trace-path"
import { PulseDot } from "./pulse-dot"

type LivingMineralFieldProps = {
  className?: string
  /** hero = stronger; section = quieter */
  intensity?: "hero" | "section"
}

const TRACE_D =
  "M48 168C120 120 180 96 240 112C300 128 340 168 400 176C460 184 520 152 580 128C640 104 700 112 752 148"

export function LivingMineralField({
  className,
  intensity = "hero",
}: LivingMineralFieldProps) {
  const { reduced } = useMotionPrefs()
  const hero = intensity === "hero"

  return (
    <div
      aria-hidden
      className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}
      data-living-mineral=""
    >
      {/* Base mineral grain — static, calm */}
      <div
        className="absolute inset-0 opacity-[0.35]"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, color-mix(in oklch, var(--g-text-primary) 8%, transparent) 1px, transparent 0)",
          backgroundSize: "28px 28px",
          maskImage: "radial-gradient(ellipse 80% 70% at 50% 40%, black 20%, transparent 75%)",
        }}
      />

      {reduced ? (
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse 55% 45% at 30% 35%, color-mix(in oklch, var(--g-emerald) 10%, transparent), transparent 70%), radial-gradient(ellipse 50% 40% at 72% 55%, color-mix(in oklch, var(--g-intelligence) 8%, transparent), transparent 68%)",
          }}
        />
      ) : (
        <>
          <motion.div
            className="absolute -left-[12%] top-[8%] h-[58%] w-[58%] rounded-full blur-3xl"
            style={{
              background:
                "radial-gradient(circle, color-mix(in oklch, var(--g-emerald) 16%, transparent) 0%, transparent 68%)",
              opacity: hero ? 0.85 : 0.45,
            }}
            animate={{ x: [0, 36, -12, 0], y: [0, 22, -18, 0], scale: [1, 1.06, 0.97, 1] }}
            transition={{ duration: 22, repeat: Infinity, ease: "easeInOut" }}
          />
          <motion.div
            className="absolute -right-[8%] top-[28%] h-[52%] w-[52%] rounded-full blur-3xl"
            style={{
              background:
                "radial-gradient(circle, color-mix(in oklch, var(--g-intelligence) 14%, transparent) 0%, transparent 70%)",
              opacity: hero ? 0.7 : 0.4,
            }}
            animate={{ x: [0, -28, 16, 0], y: [0, -20, 24, 0], scale: [1, 0.94, 1.05, 1] }}
            transition={{ duration: 26, repeat: Infinity, ease: "easeInOut" }}
          />
          <motion.div
            className="absolute bottom-[-10%] left-[28%] h-[42%] w-[48%] rounded-full blur-3xl"
            style={{
              background:
                "radial-gradient(circle, color-mix(in oklch, var(--g-approval) 10%, transparent) 0%, transparent 72%)",
              opacity: hero ? 0.55 : 0.3,
            }}
            animate={{ x: [0, 18, -22, 0], y: [0, -14, 10, 0] }}
            transition={{ duration: 30, repeat: Infinity, ease: "easeInOut" }}
          />
        </>
      )}

      {/* Hybrid B story — Intent → Tool → Approval → Verified */}
      <div
        className={cn(
          "absolute inset-x-0 top-[42%] mx-auto max-w-5xl px-8",
          hero ? "opacity-55" : "opacity-30",
        )}
      >
        <div className="relative">
          <TracePath
            d={TRACE_D}
            viewBox="0 0 800 280"
            tone="emerald"
            strokeWidth={1.25}
            label="Intent to verified execution"
            className="h-auto w-full"
          />
          <div className="pointer-events-none absolute inset-0 flex items-center justify-between px-[6%] pt-2">
            <PulseDot tone="signal" size="sm" label="Intent" />
            <PulseDot tone="intelligence" size="sm" label="Tool" />
            <PulseDot tone="approval" size="sm" label="Approval" />
            <PulseDot tone="emerald" size="sm" label="Verified" />
          </div>
        </div>
      </div>
    </div>
  )
}
