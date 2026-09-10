"use client"

/**
 * Nodus / Aceternity agent-template chrome for fleet TEAM:
 * black-sharp LogoSVG hub, spinning dual-conic glow frames, sweep connectors.
 */

import { useId, type ReactNode } from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { LogoSVG } from "@/components/marketing/nodus/logo"

/** Dual spinning conic ring — same treatment as NativeToolsHubLogo. */
export function NodusGlowFrame({
  children,
  className,
  contentClassName,
  size = "md",
}: {
  children: ReactNode
  className?: string
  contentClassName?: string
  size?: "sm" | "md" | "lg"
}) {
  const pad = size === "sm" ? "p-px" : size === "lg" ? "p-[2px]" : "p-px"
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-[var(--np-radius-md,8px)] bg-neutral-200 shadow-xl dark:bg-neutral-700",
        pad,
        className,
      )}
    >
      <div className="pointer-events-none absolute inset-0 scale-[1.45] animate-spin rounded-full [animation-duration:2s] [background-image:conic-gradient(at_center,transparent,var(--color-blue-500,#3b82f6)_20%,transparent_30%)]" />
      <div className="pointer-events-none absolute inset-0 scale-[1.45] animate-spin rounded-full [animation-delay:1s] [animation-duration:2s] [background-image:conic-gradient(at_center,transparent,var(--color-brand,#F17463)_20%,transparent_30%)]" />
      <div
        className={cn(
          "relative z-10 h-full w-full rounded-[calc(var(--np-radius-md,8px)-1px)] bg-white dark:bg-neutral-900",
          contentClassName,
        )}
      >
        {children}
      </div>
    </div>
  )
}

/** Department hub — black-sharp LogoSVG inside the glow frame. */
export function NodusDepartmentHub({
  label,
  count,
  className,
}: {
  label: string
  count: number
  className?: string
}) {
  return (
    <div className={cn("flex shrink-0 items-center gap-3", className)}>
      <NodusGlowFrame size="md" className="h-14 w-14 shrink-0 shadow-md" contentClassName="flex items-center justify-center p-3 text-black dark:text-white">
        <LogoSVG className="size-6" />
      </NodusGlowFrame>
      <div className="min-w-0">
        <p className="truncate text-sm font-medium tracking-tight text-[color:var(--g-text-primary)]">
          {label}
        </p>
        <p className="text-[11px] tabular-nums text-[color:var(--g-text-muted)]">
          {count} agent{count === 1 ? "" : "s"}
        </p>
      </div>
    </div>
  )
}

/** Horizontal sweep connector (connectors / tech-stack animation). */
export function NodusSweepConnector({
  className,
  accent = "blue",
}: {
  className?: string
  accent?: "blue" | "coral" | "amber"
}) {
  const reactId = useId()
  const gradientId = `fleet-sweep-${reactId.replace(/:/g, "")}`
  const mid =
    accent === "coral"
      ? "#F17463"
      : accent === "amber"
        ? "var(--color-yellow-500, #eab308)"
        : "var(--color-blue-500, #3b82f6)"

  return (
    <svg
      aria-hidden
      viewBox="0 0 120 2"
      fill="none"
      preserveAspectRatio="none"
      className={cn("h-[2px] w-full min-w-[2.5rem] flex-1", className)}
    >
      <line
        x1="0.5"
        y1="1"
        x2="119.5"
        y2="1"
        stroke="var(--color-line, #eaedf1)"
        strokeLinecap="round"
      />
      <line
        x1="0.5"
        y1="1"
        x2="119.5"
        y2="1"
        stroke={`url(#${gradientId})`}
        strokeLinecap="round"
      />
      <defs>
        <motion.linearGradient
          id={gradientId}
          gradientUnits="userSpaceOnUse"
          initial={{ y1: 0, y2: 1, x1: "-10%", x2: "0%" }}
          animate={{ y1: 0, y2: 1, x1: "110%", x2: "120%" }}
          transition={{
            duration: 2,
            repeat: Infinity,
            repeatType: "loop",
            ease: "easeInOut",
            repeatDelay: 1,
          }}
        >
          <stop stopColor="var(--color-line, #EAEDF1)" />
          <stop offset="0.5" stopColor={mid} />
          <stop offset="1" stopColor="var(--color-line, #EAEDF1)" />
        </motion.linearGradient>
      </defs>
    </svg>
  )
}

const SWEEP_ACCENTS = ["blue", "coral", "amber"] as const

export function sweepAccentForIndex(index: number): (typeof SWEEP_ACCENTS)[number] {
  return SWEEP_ACCENTS[index % SWEEP_ACCENTS.length]!
}
