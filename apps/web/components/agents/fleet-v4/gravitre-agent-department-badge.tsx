"use client"

import { cn } from "@/lib/utils"
import { DEPARTMENT_ACCENT } from "./identity-tokens"
import type { AgentDepartmentId } from "./types"

export function GravitreAgentDepartmentBadge({
  department,
  label,
  className,
}: {
  department: AgentDepartmentId
  label?: string
  className?: string
}) {
  const meta = DEPARTMENT_ACCENT[department]
  return (
    <span
      className={cn(
        "text-[10px] font-medium uppercase tracking-wide",
        meta.accentClass,
        className,
      )}
    >
      {label ?? meta.label}
    </span>
  )
}
