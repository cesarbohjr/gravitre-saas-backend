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
        "flex min-w-[6.5rem] flex-col items-center gap-1.5 rounded-xl border bg-white px-2.5 py-2 text-center shadow-sm",
        waiting && "border-amber-400",
        failed && "border-red-400",
        active && !waiting && !failed && "border-[color:var(--color-brand,#16a374)]",
        !active && !waiting && !failed && "border-[color:var(--color-line,#eaedf1)] opacity-70",
      )}
    >
      <Icon
        className={cn(
          "h-4 w-4 text-[color:var(--g-text-secondary)]",
          active && "text-[color:var(--color-brand,#16a374)]",
          waiting && "text-amber-600",
          failed && "text-red-600",
        )}
        aria-hidden
      />
      <span className="text-[11px] font-semibold leading-tight text-[color:var(--g-text-secondary)]">{label}</span>
      <span className="text-[9px] uppercase tracking-wide text-[color:var(--g-text-muted)]">Capability</span>
    </div>
  )
}
