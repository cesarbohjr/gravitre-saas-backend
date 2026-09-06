"use client"

/**
 * StatusChip — canonical UI 3.0 status surface.
 * Uses STATUS / STATUS_DOT from design-system. Never invent TRAINED/live claims.
 */

import Link from "next/link"
import { cn } from "@/lib/utils"
import {
  RADIUS,
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
}: StatusChipProps) {
  const resolved = tone ?? (status ? resolveStatusTone(status) : "idle")
  const shouldPulse = pulse || resolved === "running"
  const classes = cn(
    "inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium",
    RADIUS.control,
    STATUS[resolved],
    className,
  )

  const body = (
    <>
      {dot ? (
        shouldPulse ? (
          <PulseDot tone={resolved === "running" ? "intelligence" : "signal"} size="sm" />
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
