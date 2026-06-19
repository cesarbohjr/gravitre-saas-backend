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
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-muted/20 px-6 py-12 text-center">
      {visual ? (
        <div className="mb-1 w-full">{visual}</div>
      ) : (
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-muted text-muted-foreground">
          <Icon className="h-6 w-6" />
        </div>
      )}
      <h3 className="mt-4 text-sm font-semibold">{title}</h3>
      <p className="mt-1 max-w-sm text-pretty text-sm leading-relaxed text-muted-foreground">
        {description}
      </p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}
