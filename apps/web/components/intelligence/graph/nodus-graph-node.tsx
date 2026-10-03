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
    <div className={cn("flex max-w-[8.5rem] flex-col items-center gap-1.5", className)}>
      <div
        className={cn(
          "relative shrink-0 overflow-hidden rounded-[10px] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] p-px shadow-[0_12px_30px_-26px_rgba(16,24,22,.65)]",
          box,
          selected && "ring-2 ring-[color:var(--g-brand)] ring-offset-1",
          active && "ring-1 ring-[color:var(--g-emerald)]",
        )}
      >
        {spin ? <div className="absolute inset-x-1 bottom-0 h-[2px] overflow-hidden rounded-full bg-[color:var(--g-emerald-pale)]"><div className="h-full w-1/2 animate-[g-node-route_1.2s_ease-in-out_infinite] rounded-full bg-[color:var(--g-emerald)]" /></div> : null}
        <div className="relative z-20 flex h-full w-full items-center justify-center rounded-[5px] bg-background text-[color:var(--g-emerald-deep)]">
          <Icon className={iconSize} aria-hidden />
        </div>
      </div>
      {showLabel ? (
        <span className="min-w-0 text-center" title={label}>
          <span className="line-clamp-2 block text-[11px] font-semibold leading-snug text-[color:var(--g-text-secondary)]">
            {label}
          </span>
          {sublabel ? (
            <span className="mt-0.5 block truncate text-[10px] capitalize text-[color:var(--g-text-muted)]">
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
