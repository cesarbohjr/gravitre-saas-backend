import React from "react"
import { cn } from "@/lib/utils"

/**
 * macOS-style window outline for product screenshots (Feature Overlays design):
 * white title bar with traffic lights and a centred title pill, plus optional
 * floating chips pinned to the frame corners. Chips repeat what the screen
 * already shows or what the product does; they never carry invented metrics.
 */
export type AppWindowChip = {
  label: string
  /** Corner the chip hangs off. */
  at: "top-left" | "top-right" | "bottom-left" | "bottom-right"
  tone?: "green" | "amber" | "slate"
}

const TONE: Record<NonNullable<AppWindowChip["tone"]>, string> = {
  green: "bg-[#19c37d]",
  amber: "bg-[#e2a33a]",
  slate: "bg-[#5b6e7a]",
}

const AT: Record<AppWindowChip["at"], string> = {
  "top-left": "-top-3.5 left-4 md:-left-4",
  "top-right": "-top-3.5 right-4 md:-right-4",
  "bottom-left": "-bottom-3.5 left-4 md:-left-4",
  "bottom-right": "-bottom-3.5 right-4 md:-right-4",
}

export function AppWindow({
  title,
  chips = [],
  children,
  className,
}: {
  title: string
  chips?: AppWindowChip[]
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("relative", className)}>
      <div className="overflow-hidden rounded-lg border border-[#e2e5ea] bg-white shadow-[0_24px_60px_-24px_rgba(20,21,19,0.35),0_1px_4px_rgba(0,0,0,0.06)] md:rounded-xl">
        <div className="relative flex h-7 items-center border-b border-[#e2e5ea] bg-white px-3 md:h-9 md:px-4">
          <div aria-hidden className="flex gap-1.5">
            <span className="size-2 rounded-full bg-[#ff5f57] md:size-3" />
            <span className="size-2 rounded-full bg-[#febc2e] md:size-3" />
            <span className="size-2 rounded-full bg-[#28c840] md:size-3" />
          </div>
          <span className="absolute left-1/2 -translate-x-1/2 rounded-md bg-[#f1f2f4] px-2.5 py-0.5 text-[9px] font-medium text-[#6b7280] md:px-3 md:text-[11px]">
            {title}
          </span>
        </div>
        {children}
      </div>
      {chips.map((chip) => (
        <div
          key={chip.label}
          className={cn(
            "absolute z-10 hidden items-center gap-2 rounded-full border border-[#e2e5ea] bg-white px-3 py-1.5 text-xs font-medium text-[#0f1117] shadow-[0_4px_16px_rgba(0,0,0,0.10),0_1px_4px_rgba(0,0,0,0.06)] sm:flex",
            AT[chip.at],
          )}
        >
          <i aria-hidden className={cn("mk-scene-pulse size-2 rounded-full", TONE[chip.tone ?? "green"])} />
          {chip.label}
        </div>
      ))}
    </div>
  )
}
