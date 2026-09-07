"use client"

import type { LucideIcon } from "lucide-react"
import type { ReactNode } from "react"

export function FederationEmptyState({
  icon: Icon,
  visual,
  title,
  description,
  action,
}: {
  icon: LucideIcon
  /** Optional richer illustration rendered instead of the default icon tile. */
  visual?: ReactNode
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-[var(--np-radius-lg)] border border-dashed border-divide bg-[color:var(--g-surface-2)] px-6 py-12 text-center shadow-[var(--np-shadow)]">
      {visual ? (
        <div className="mb-1 w-full">{visual}</div>
      ) : (
        <div className="flex h-12 w-12 items-center justify-center rounded-[var(--np-radius-md)] bg-[color:var(--g-surface-1)] text-[color:var(--g-text-muted)] border border-divide">
          <Icon className="h-6 w-6" />
        </div>
      )}
      <h3 className="mt-4 text-sm font-semibold text-[color:var(--g-text-primary)]">{title}</h3>
      <p className="mt-1 max-w-sm text-pretty text-sm leading-relaxed text-[color:var(--g-text-muted)]">
        {description}
      </p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}
