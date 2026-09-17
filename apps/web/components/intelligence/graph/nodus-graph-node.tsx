"use client"

import type { ComponentType, SVGProps } from "react"
import type { MapNodeKind } from "@/components/intelligence/map/map-topology"
import {
  NucleoAgent,
  NucleoBell,
  NucleoHistory,
  NucleoSearch,
  NucleoSettings,
  NucleoWorkflow,
} from "@/components/icons/nucleo/semantic"
import { cn } from "@/lib/utils"

type IconProps = SVGProps<SVGSVGElement> & { size?: number | string }

/** One licensed Nucleo Sharp glyph per map node kind — never Phosphor on this canvas. */
export const MAP_KIND_NUCLEO: Record<MapNodeKind, ComponentType<IconProps>> = {
  department: NucleoWorkflow,
  agent: NucleoAgent,
  "entity-type": NucleoSearch,
  model: NucleoSettings,
  signal: NucleoBell,
  learning: NucleoHistory,
}

/**
 * Nodus connectors/agents graph tile — white rounded square, contained conic
 * spin, no overflowing rings.
 */
export function NodusGraphNodeTile({
  icon: Icon,
  label,
  sublabel,
  active = false,
  selected = false,
  showLabel = true,
  reduced = false,
  size = "md",
  className,
}: {
  icon: ComponentType<IconProps>
  label: string
  sublabel?: string
  active?: boolean
  selected?: boolean
  showLabel?: boolean
  reduced?: boolean
  size?: "sm" | "md"
  className?: string
}) {
  const box = size === "sm" ? "h-11 w-11 sm:h-12 sm:w-12" : "h-12 w-12 sm:h-14 sm:w-14"
  const iconSize = size === "sm" ? "h-5 w-5" : "h-6 w-6"
  const spin = active && !reduced

  return (
    <div className={cn("flex max-w-[7.5rem] flex-col items-center gap-1.5", className)}>
      <div
        className={cn(
          "relative shrink-0 overflow-hidden rounded-md bg-gray-200 p-px shadow-xl dark:bg-neutral-700",
          box,
          selected && "ring-2 ring-[color:var(--g-brand)] ring-offset-1",
          active && "ring-1 ring-[color:var(--color-brand,#16a374)]",
        )}
      >
        {spin ? (
          <>
            <div className="absolute inset-0 scale-[1.4] animate-spin rounded-full [animation-duration:2s] [background-image:conic-gradient(at_center,transparent,var(--color-blue-500)_20%,transparent_30%)]" />
            <div className="absolute inset-0 scale-[1.4] animate-spin rounded-full [animation-delay:1s] [animation-duration:2s] [background-image:conic-gradient(at_center,transparent,var(--color-brand,#16a374)_20%,transparent_30%)]" />
          </>
        ) : null}
        <div className="relative z-20 flex h-full w-full items-center justify-center rounded-[5px] bg-white text-[color:var(--color-brand,#16a374)] dark:bg-neutral-900">
          <Icon className={iconSize} aria-hidden />
        </div>
      </div>
      {showLabel ? (
        <span className="min-w-0 text-center">
          <span className="block truncate text-[11px] font-semibold text-[color:var(--g-text-secondary)]">
            {label}
          </span>
          {sublabel ? (
            <span className="block truncate text-[10px] capitalize text-[color:var(--g-text-muted)]">
              {sublabel}
            </span>
          ) : null}
        </span>
      ) : (
        <span className="sr-only">{label}</span>
      )}
    </div>
  )
}
