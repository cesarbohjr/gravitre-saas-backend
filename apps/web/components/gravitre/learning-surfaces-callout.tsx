"use client"

import Link from "next/link"
import { cn } from "@/lib/utils"
import { APP_ROUTES } from "@/lib/app-routes"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { TYPE } from "@/lib/design-system"

export type LearningSurfaceId = "org-learning" | "agent-training" | "model-registry"

const SURFACES: Array<{
  id: LearningSurfaceId
  href: string
  title: string
}> = [
  {
    id: "org-learning",
    href: APP_ROUTES.learning,
    title: SURFACE_COPY.learning.title,
  },
  {
    id: "agent-training",
    href: APP_ROUTES.training,
    title: SURFACE_COPY.training.title,
  },
  {
    id: "model-registry",
    href: APP_ROUTES.models,
    title: SURFACE_COPY.models.title,
  },
]

export function LearningSurfacesCallout({
  current,
  className,
}: {
  current: LearningSurfaceId
  className?: string
  compact?: boolean
}) {
  const loop = SURFACE_COPY.learningLoop

  return (
    <nav aria-label="Learning loop navigation" className={cn("space-y-1", className)}>
      <p className={TYPE.meta}>{loop.title}</p>
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        {SURFACES.map((surface) => {
          const isCurrent = surface.id === current
          return (
            <Link
              key={surface.id}
              href={surface.href}
              aria-current={isCurrent ? "page" : undefined}
              className={cn(
                TYPE.meta,
                "underline-offset-4",
                isCurrent
                  ? "text-[color:var(--g-text-primary)] underline"
                  : "text-[color:var(--g-text-muted)] hover:text-[color:var(--g-text-primary)]",
              )}
            >
              {surface.title}
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
