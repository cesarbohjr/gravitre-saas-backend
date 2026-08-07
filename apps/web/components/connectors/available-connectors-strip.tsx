"use client"

import { useEffect, useRef } from "react"
import { ArrowRight } from "lucide-react"
import { ConnectorIcon } from "@/components/gravitre/connector-icon"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export type AvailableConnectorEntry = {
  vendorKey: string
  type: string
  description: string
}

type AvailableConnectorsStripProps = {
  entries: AvailableConnectorEntry[]
  onBrowseAll: () => void
  onSelect: (type: string) => void
  showBrowseAll?: boolean
  className?: string
}

export function AvailableConnectorsStrip({
  entries,
  onBrowseAll,
  onSelect,
  showBrowseAll = true,
  className,
}: AvailableConnectorsStripProps) {
  const trackRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const track = trackRef.current
    if (!track || entries.length < 4) return

    let frame = 0
    let direction = 1
    let paused = false

    const onEnter = () => {
      paused = true
    }
    const onLeave = () => {
      paused = false
    }

    track.addEventListener("mouseenter", onEnter)
    track.addEventListener("focusin", onEnter)
    track.addEventListener("mouseleave", onLeave)
    track.addEventListener("focusout", onLeave)

    const tick = () => {
      if (!paused && track.scrollWidth > track.clientWidth + 8) {
        track.scrollLeft += direction * 0.6
        if (track.scrollLeft + track.clientWidth >= track.scrollWidth - 2) direction = -1
        if (track.scrollLeft <= 0) direction = 1
      }
      frame = window.requestAnimationFrame(tick)
    }

    frame = window.requestAnimationFrame(tick)
    return () => {
      window.cancelAnimationFrame(frame)
      track.removeEventListener("mouseenter", onEnter)
      track.removeEventListener("focusin", onEnter)
      track.removeEventListener("mouseleave", onLeave)
      track.removeEventListener("focusout", onLeave)
    }
  }, [entries.length])

  if (entries.length === 0) return null

  return (
    <section
      aria-label="Available connectors"
      className={cn(
        // min-w-0 keeps this strip inside AppShell (overflow-x-hidden); without
        // it the card track grows to content width and the right edge clips.
        "w-full min-w-0 border-b border-border bg-secondary/20 px-4 py-2.5 md:px-6",
        className,
      )}
    >
      <div className="mb-2 flex min-w-0 flex-wrap items-center justify-between gap-x-2 gap-y-0.5">
        <div className="flex min-w-0 flex-wrap items-baseline gap-x-2">
          <h2 className="text-sm font-semibold text-foreground">Available connectors</h2>
          <p className="text-xs text-muted-foreground">
            Self-serve integrations ready to connect from this workspace.
          </p>
        </div>
        {showBrowseAll && (
          <Button variant="outline" size="sm" className="h-8 shrink-0" onClick={onBrowseAll}>
            Browse all
          </Button>
        )}
      </div>
      <div
        ref={trackRef}
        className="flex w-full min-w-0 max-w-full gap-2 overflow-x-auto overscroll-x-contain pb-1 scroll-smooth [scrollbar-gutter:stable] [scrollbar-width:thin]"
      >
        {entries.map((entry) => (
          <button
            key={entry.vendorKey}
            type="button"
            onClick={() => onSelect(entry.type)}
            className="group flex w-[200px] max-w-[80vw] shrink-0 items-center gap-3 rounded-xl border border-border bg-card px-3 py-2.5 text-left transition-colors hover:border-blue-500/30 hover:bg-blue-500/5"
          >
            <ConnectorIcon vendor={entry.type} size="sm" />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5">
                <span className="truncate text-sm font-medium capitalize text-foreground">{entry.type}</span>
                <span className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[9px] font-medium uppercase text-emerald-500">
                  Available
                </span>
              </div>
              <p className="truncate text-[11px] text-muted-foreground">{entry.description}</p>
            </div>
            <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
          </button>
        ))}
      </div>
    </section>
  )
}
