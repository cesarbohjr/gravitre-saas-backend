"use client"

import { cn } from "@/lib/utils"
import type { ComponentType, SVGProps } from "react"

type Icon = ComponentType<SVGProps<SVGSVGElement> & { className?: string; size?: number }>

export function GravitreAgentNode({
  label,
  icon: Icon,
  active = false,
  waiting = false,
  failed = false,
}: {
  label: string
  icon: Icon
  active?: boolean
  waiting?: boolean
  failed?: boolean
}) {
  return (
    <div
      className={cn(
        "flex min-w-[6.5rem] flex-col items-center gap-1.5 rounded-xl border bg-card px-2.5 py-2 text-center shadow-sm",
        waiting && "border-warning/60",
        failed && "border-destructive/60",
        active && !waiting && !failed && "border-brand",
        !active && !waiting && !failed && "border-line opacity-70",
      )}
    >
      <Icon
        className={cn(
          "h-4 w-4 text-[color:var(--g-text-secondary)]",
          active && "text-brand",
          waiting && "text-warning-text",
          failed && "text-danger-text",
        )}
        aria-hidden
      />
      <span className="text-[11px] font-semibold leading-tight text-[color:var(--g-text-secondary)]">{label}</span>
      <span className="text-[9px] uppercase tracking-wide text-[color:var(--g-text-muted)]">Capability</span>
    </div>
  )
}
