"use client"

/**
 * PageIntro — production page-family introduction (G-STRUCT A1).
 * Operating · Expert · Empty · Immersive — not one universal header.
 */

import type { ReactNode } from "react"
import { PAGE_FAMILY, TYPE, type PageFamilyId } from "@/lib/design-system"
import { cn } from "@/lib/utils"

export function PageIntro({
  family,
  title,
  lead,
  actions,
  eyebrow,
  children,
  className,
}: {
  family: PageFamilyId
  title: ReactNode
  lead?: ReactNode
  actions?: ReactNode
  eyebrow?: ReactNode
  children?: ReactNode
  className?: string
}) {
  const spec = PAGE_FAMILY[family]
  return (
    <header
      data-page-family={family}
      data-slot="page-intro"
      className={cn(spec.shell, className)}
    >
      {eyebrow ? <p className={TYPE.eyebrow}>{eyebrow}</p> : null}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-1">
          <h1 className={spec.title}>{title}</h1>
          {lead ? <p className={spec.lead}>{lead}</p> : null}
        </div>
        {actions ? <div className={spec.actions}>{actions}</div> : null}
      </div>
      {children}
    </header>
  )
}
