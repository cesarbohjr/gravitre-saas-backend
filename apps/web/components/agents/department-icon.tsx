"use client"

import type { ReactNode } from "react"
import { cn } from "@/lib/utils"
import { DEPARTMENT_ICONS, departmentIdFor } from "@/lib/department-icons"

const TILE_PX = { xs: 22, sm: 28, md: 36, lg: 46, xl: 56 } as const
const GLYPH_PX = { xs: 12, sm: 15, md: 18, lg: 22, xl: 26 } as const

export type DepartmentIconSize = keyof typeof TILE_PX

/**
 * An agent's mark: its department's icon on the department tint. Pass any
 * department label or id; unknown or missing departments read as General.
 * `children` sits inside the tile (status dots).
 */
export function DepartmentIcon({
  department,
  size = "md",
  className,
  children,
  title,
}: {
  department: string | null | undefined
  size?: DepartmentIconSize
  className?: string
  children?: ReactNode
  title?: string
}) {
  const id = departmentIdFor(department)
  const Icon = DEPARTMENT_ICONS[id]
  const px = TILE_PX[size]
  return (
    <span
      className={cn("dept-tile", className)}
      data-dept={id}
      title={title}
      aria-hidden={title ? undefined : true}
      style={{ width: px, height: px, borderRadius: Math.round(px * 0.28) }}
    >
      <Icon size={GLYPH_PX[size]} strokeWidth={1.9} aria-hidden />
      {children}
    </span>
  )
}

/** Bare department glyph in the department ink, for chips and group headers. */
export function DepartmentGlyph({
  department,
  size = 14,
  className,
}: {
  department: string | null | undefined
  size?: number
  className?: string
}) {
  const id = departmentIdFor(department)
  const Icon = DEPARTMENT_ICONS[id]
  return <Icon size={size} strokeWidth={2} className={cn("dept-glyph", className)} data-dept={id} aria-hidden />
}
