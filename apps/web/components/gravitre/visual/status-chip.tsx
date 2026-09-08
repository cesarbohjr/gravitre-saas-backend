"use client"

/**
 * StatusChip — canonical Nodus soft-pill / plain status surface.
 * Uses STATUS / STATUS_DOT / CHIP from design-system. Never invent TRAINED/live claims.
 */

import Link from "next/link"
import { cn } from "@/lib/utils"
import {
  CHIP,
  STATUS,
  STATUS_DOT,
  resolveStatusTone,
  type StatusTone,
} from "@/lib/design-system"
import { PulseDot } from "./pulse-dot"

export type StatusChipProps = {
  children: React.ReactNode
  tone?: StatusTone
  /** Raw API status — resolved via resolveStatusTone when tone omitted. */
  status?: string
  href?: string
  className?: string
  /** Show tone dot; use pulse for running / thinking intelligence. */
  dot?: boolean
  pulse?: boolean
  title?: string
  /**
   * `chip` — soft filled pill (default, Nodus model-tag style).
   * `plain` — colored dot + graphite label (Nodus status column).
   */
  appearance?: "chip" | "plain"
}

export function StatusChip({
  children,
  tone,
  status,
  href,
  className,
  dot = true,
  pulse = false,
  title,
  appearance = "chip",
}: StatusChipProps) {
  const resolved = tone ?? (status ? resolveStatusTone(status) : "idle")
  const shouldPulse = pulse || resolved === "running"
  const classes = cn(
    appearance === "plain" ? CHIP.plain : cn(CHIP.base, STATUS[resolved]),
    className,
  )

  const body = (
    <>
      {dot ? (
        shouldPulse ? (
          <PulseDot tone={resolved === "running" ? "emerald" : "signal"} size="sm" />
        ) : (
          <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", STATUS_DOT[resolved])} aria-hidden />
        )
      ) : null}
      {children}
    </>
  )

  if (href) {
    return (
      <Link href={href} title={title} className={cn(classes, "transition-opacity hover:opacity-90")}>
        {body}
      </Link>
    )
  }

  return (
    <span title={title} className={classes}>
      {body}
    </span>
  )
}
