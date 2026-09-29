"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { ChevronLeft, ChevronRight, Plus } from "lucide-react"
import { ProviderLogo } from "@/components/gravitre/provider-logo"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export type AvailableConnectorEntry = {
  vendorKey: string
  type: string
  description: string
  category?: string
}

type AvailableConnectorsStripProps = {
  entries: AvailableConnectorEntry[]
  onBrowseAll: () => void
  onSelect: (type: string) => void
  showBrowseAll?: boolean
  className?: string
}

/** Provider discovery rail: real vendor marks on a flat surface, scrolls horizontally. */
export function AvailableConnectorsStrip({
  entries,
  onBrowseAll,
  onSelect,
  showBrowseAll = true,
  className,
}: AvailableConnectorsStripProps) {
  const trackRef = useRef<HTMLDivElement>(null)
  const [edges, setEdges] = useState({ start: true, end: true })

  const measure = useCallback(() => {
    const track = trackRef.current
    if (!track) return
    setEdges({
      start: track.scrollLeft <= 2,
      end: track.scrollLeft + track.clientWidth >= track.scrollWidth - 2,
    })
  }, [])

  useEffect(() => {
    const track = trackRef.current
    if (!track) return
    const frame = requestAnimationFrame(measure)
    const observer = new ResizeObserver(measure)
    observer.observe(track)
    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
    }
  }, [measure, entries.length])

  const page = (direction: 1 | -1) => {
    const track = trackRef.current
    if (!track) return
    track.scrollBy({ left: direction * Math.max(240, track.clientWidth * 0.8), behavior: "smooth" })
  }

  if (entries.length === 0) return null

  return (
    <section
      aria-labelledby="connectors-discovery-heading"
      data-review-surface="connectors-discovery"
      className={cn("w-full min-w-0 border-b border-[color:var(--g-border-default)] px-4 py-3 md:px-6", className)}
    >
      <div className="mb-2.5 flex min-w-0 items-center justify-between gap-2">
        <div className="flex min-w-0 flex-wrap items-baseline gap-x-2">
          <h2 id="connectors-discovery-heading" className="text-[13px] font-semibold text-foreground">
            Discover systems
          </h2>
          <p className="text-[12px] text-muted-foreground">{entries.length} available to connect</p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => page(-1)}
            disabled={edges.start}
            aria-label="Scroll systems left"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => page(1)}
            disabled={edges.end}
            aria-label="Scroll systems right"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
          {showBrowseAll ? (
            <Button variant="outline" size="sm" className="ml-1 h-7 text-[12px]" onClick={onBrowseAll}>
              Browse all
            </Button>
          ) : null}
        </div>
      </div>
      <div
        ref={trackRef}
        onScroll={measure}
        className="flex w-full min-w-0 max-w-full snap-x gap-2 overflow-x-auto overscroll-x-contain pb-1 [scrollbar-width:thin]"
      >
        {entries.map((entry) => (
          <button
            key={entry.vendorKey}
            type="button"
            onClick={() => onSelect(entry.type)}
            data-discovery-provider={entry.vendorKey}
            title={entry.description || entry.type}
            className="group flex w-[176px] shrink-0 snap-start items-center gap-2.5 rounded-md border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] px-3 py-2.5 text-left transition-colors hover:border-[color:var(--g-border-strong)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:border-[color:var(--graphite-700)] dark:bg-[color:var(--carbon-900)]"
          >
            <ProviderLogo provider={entry.vendorKey} label={entry.type} size="lg" decorative />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13px] font-medium text-foreground">{entry.type}</span>
              <span className="block truncate text-[11.5px] text-muted-foreground">{entry.category || "Connector"}</span>
            </span>
            <Plus
              className="h-3.5 w-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
              aria-hidden
            />
          </button>
        ))}
      </div>
    </section>
  )
}
