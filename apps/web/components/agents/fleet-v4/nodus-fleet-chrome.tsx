"use client"

/**
 * Nodus / Aceternity agent-template chrome for fleet TEAM:
 * department icon+label → Gravitre LogoSVG hub → agent cards.
 */

import { useId, type ComponentType, type ReactNode, type SVGProps } from "react"
import { motion } from "framer-motion"
import {
  Briefcase,
  Code2,
  Cog,
  Headphones,
  Landmark,
  Megaphone,
  Shield,
  Users,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { LogoSVG } from "@/components/marketing/nodus/logo"
import type { AgentDepartmentId } from "./types"

type IconComponent = ComponentType<SVGProps<SVGSVGElement> & { size?: number | string }>

/** Crisp black outline icons — distinct per department. */
export const DEPARTMENT_OUTLINE_ICONS: Record<AgentDepartmentId, IconComponent> = {
  sales: Briefcase as IconComponent,
  customer_success: Headphones as IconComponent,
  finance: Landmark as IconComponent,
  operations: Cog as IconComponent,
  engineering: Code2 as IconComponent,
  marketing: Megaphone as IconComponent,
  security: Shield as IconComponent,
  general: Users as IconComponent,
}

/** Dual spinning conic ring — NativeToolsHubLogo treatment. */
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

/** Left rail — small black department icon + full label (no truncation). */
export function NodusDepartmentLabel({
  department,
  label,
  count,
  className,
}: {
  department: AgentDepartmentId
  label: string
  count?: number
  className?: string
}) {
  const Icon = DEPARTMENT_OUTLINE_ICONS[department]
  return (
    <div className={cn("relative flex items-center gap-2.5", className)}>
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-neutral-200 bg-white text-black shadow-sm dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-100">
        <Icon className="size-[15px]" strokeWidth={1.75} aria-hidden />
      </span>
      <div className="min-w-0">
        <span
          className="block whitespace-nowrap text-sm font-medium leading-tight text-[color:var(--g-text-primary)]"
          title={label}
        >
          {label}
        </span>
        {count != null ? (
          <span className="mt-0.5 block whitespace-nowrap text-[10px] tabular-nums text-[color:var(--g-text-muted)]">
            {count} agent{count === 1 ? "" : "s"}
          </span>
        ) : null}
      </div>
    </div>
  )
}

/** Center hub — Gravitre black-sharp mark only (not a department). */
export function NodusGravitreHub({ className }: { className?: string }) {
  return (
    <NodusGlowFrame
      size="md"
      className={cn("h-14 w-14 shrink-0 shadow-md sm:h-16 sm:w-16", className)}
      contentClassName="flex items-center justify-center p-3 text-black dark:text-white sm:p-3.5"
    >
      <LogoSVG className="size-6" />
    </NodusGlowFrame>
  )
}

/** @deprecated Prefer NodusDepartmentLabel + NodusGravitreHub */
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
      <NodusGravitreHub />
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

/**
 * Elbow connector from a left label into a vertical spine (TopSVG / BottomSVG style).
 * variant: top bends down into spine, bottom bends up, mid is straight.
 */
export function NodusConvergeConnector({
  variant = "mid",
  accent = "blue",
  className,
}: {
  variant?: "top" | "mid" | "bottom"
  accent?: "blue" | "coral" | "amber"
  className?: string
}) {
  const reactId = useId()
  const gid = `fleet-converge-${reactId.replace(/:/g, "")}`
  const mid =
    accent === "coral"
      ? "#F17463"
      : accent === "amber"
        ? "var(--color-yellow-500, #eab308)"
        : "var(--color-blue-500, #3b82f6)"

  if (variant === "mid") {
    return <NodusSweepConnector accent={accent} className={cn("w-full max-w-[12rem]", className)} />
  }

  const h = 32
  const w = 160
  const yLine = variant === "top" ? 1 : h - 1
  const yEnd = variant === "top" ? h : 1

  return (
    <svg
      aria-hidden
      width={w}
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      fill="none"
      className={cn("shrink-0", className)}
    >
      <line
        x1="0.5"
        y1={yLine}
        x2={w - 0.5}
        y2={yLine}
        stroke="var(--color-line, #eaedf1)"
        strokeLinecap="round"
      />
      <line
        x1={w - 0.5}
        y1={yLine}
        x2={w - 0.5}
        y2={yEnd}
        stroke="var(--color-line, #eaedf1)"
        strokeLinecap="round"
      />
      <line
        x1="0.5"
        y1={yLine}
        x2={w - 0.5}
        y2={yLine}
        stroke={`url(#${gid})`}
        strokeLinecap="round"
      />
      <defs>
        <motion.linearGradient
          id={gid}
          gradientUnits="userSpaceOnUse"
          initial={{ x1: "-20%", x2: "0%", y1: 0, y2: 1 }}
          animate={{ x1: "105%", x2: "120%", y1: 0, y2: 1 }}
          transition={{
            duration: 2,
            repeat: Infinity,
            repeatType: "loop",
            ease: "easeInOut",
            repeatDelay: 1,
          }}
        >
          <stop stopColor="var(--color-line, #EAEDF1)" />
          <stop offset="0.33" stopColor={mid} />
          <stop offset="0.66" stopColor={mid} />
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

export function convergeVariantForIndex(
  index: number,
  total: number,
): "top" | "mid" | "bottom" {
  if (total <= 1) return "mid"
  if (index === 0) return "top"
  if (index === total - 1) return "bottom"
  return "mid"
}
