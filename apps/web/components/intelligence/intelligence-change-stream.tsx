"use client"

import { AnimatePresence, motion } from "framer-motion"
import type { IntelligencePageContextResponse } from "@/lib/api"
import type { IntelligenceChangeEvent } from "@/lib/intelligence/build-change-events"
import type { IntelligenceMapLens } from "@/components/intelligence/map/intelligence-map-lens"
import type { IntelligenceMapSelection } from "@/components/intelligence/map/intelligence-map"
import { EvidenceChip } from "@/components/gravitre/creative-grammar"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

export function IntelligenceChangeStream({
  open,
  isMobile,
  reducedMotion,
  activeLens,
  streamEvents,
  selectedEventId,
  pageContext,
  onSelectEvent,
  onSelectionChange,
  className,
}: {
  open: boolean
  isMobile: boolean
  reducedMotion: boolean
  activeLens: IntelligenceMapLens
  streamEvents: IntelligenceChangeEvent[]
  selectedEventId: string | null
  pageContext?: IntelligencePageContextResponse | null
  onSelectEvent: (eventId: string | null) => void
  onSelectionChange: (selection: IntelligenceMapSelection) => void
  className?: string
}) {
  const list = (
    <>
      <p className={cn(TYPE.eyebrow, "px-3 pt-3")}>Change stream · I2</p>
      <p className={cn(TYPE.meta, "px-3 pb-2")}>Contextual · filtered by {activeLens}</p>
      <ul className={cn("overflow-y-auto px-2 pb-3", isMobile ? "max-h-[50vh]" : "max-h-[52vh]")}>
        {streamEvents.length === 0 ? (
          <li className={cn(TYPE.meta, "px-2 py-3")}>No change events in this lens window.</li>
        ) : (
          streamEvents.map((ev) => (
            <li key={ev.id}>
              <button
                type="button"
                className={cn(
                  "w-full rounded-md px-2 py-2 text-left hover:bg-[color:var(--g-surface-2)]",
                  selectedEventId === ev.id && "bg-[color:var(--g-surface-2)]",
                )}
                onClick={() => {
                  onSelectEvent(ev.id)
                  if (ev.focusNodeIds[0] && pageContext?.graph) {
                    const node = pageContext.graph.nodes.find((n) => n.id === ev.focusNodeIds[0])
                    if (node) {
                      onSelectionChange({
                        kind: "satellite",
                        node: {
                          id: String(node.id),
                          kind: "entity-type",
                          label: String(node.businessLabel ?? node.id),
                          sublabel: String(node.type ?? ""),
                          emphasis: 1,
                        },
                      })
                    }
                  }
                }}
              >
                <EvidenceChip label={ev.kind} tone="evidence" />
                <p className="mt-1 text-xs font-semibold text-[color:var(--g-text-primary)]">{ev.title}</p>
                {ev.at ? <p className={cn(TYPE.meta, "mt-0.5")}>{ev.at}</p> : null}
              </button>
            </li>
          ))
        )}
      </ul>
    </>
  )

  if (isMobile) {
    if (!open) return null
    return (
      <aside
        className={cn(
          "mb-3 w-full shrink-0 overflow-hidden rounded-lg border border-[color:var(--g-border-subtle)] bg-[color:var(--g-canvas)]",
          className,
        )}
        data-testid="intel-i2-stream"
      >
        {list}
      </aside>
    )
  }

  return (
    <AnimatePresence>
      {open ? (
        <motion.aside
          initial={reducedMotion ? false : { width: 0, opacity: 0 }}
          animate={{ width: 260, opacity: 1 }}
          exit={reducedMotion ? undefined : { width: 0, opacity: 0 }}
          className={cn(
            "hidden w-[260px] shrink-0 overflow-hidden border-r border-[color:var(--g-border-subtle)] bg-[color:var(--g-canvas)] md:block",
            className,
          )}
          data-testid="intel-i2-stream"
        >
          {list}
        </motion.aside>
      ) : null}
    </AnimatePresence>
  )
}
