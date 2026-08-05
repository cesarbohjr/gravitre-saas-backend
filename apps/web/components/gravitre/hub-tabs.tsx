"use client"

/**
 * Shared segmented tab strip for the Activity / Agents / Intelligence / Settings hubs.
 *
 * Replaces two near-identical hand-rolled copies (activity page + agents-hub-tabs)
 * that had drifted apart and were missing the keyboard support `role="tablist"`
 * implies. Supports both navigation tabs (`href`) and local state tabs
 * (`onSelect`), so every hub gets the same affordance regardless of whether the
 * tab changes the route or just the panel.
 */

import Link from "next/link"
import { useId, useRef, type KeyboardEvent } from "react"
import { motion, useReducedMotion } from "framer-motion"
import { cn } from "@/lib/utils"

export interface HubTabItem<T extends string = string> {
  id: T
  label: string
  /** Optional count shown as a trailing pill. */
  count?: number
  /** When set the tab navigates instead of firing `onSelect`. */
  href?: string
}

export interface HubTabsProps<T extends string> {
  tabs: ReadonlyArray<HubTabItem<T>>
  active: T
  onSelect?: (id: T) => void
  /** Accessible name for the tablist, e.g. "Activity views". */
  ariaLabel: string
  className?: string
  /** `sm` tightens padding for dense header rows. */
  size?: "sm" | "default"
}

export function HubTabs<T extends string>({
  tabs,
  active,
  onSelect,
  ariaLabel,
  className,
  size = "default",
}: HubTabsProps<T>) {
  const refs = useRef<Array<HTMLElement | null>>([])
  // Scopes the shared-layout pill to this instance, so two tab strips on one
  // page can't animate into each other.
  const indicatorLayoutId = useId()
  const reduceMotion = useReducedMotion()

  // `role="tablist"` promises arrow-key navigation to screen reader and
  // keyboard users; without this the strip is a tab trap where only clicking
  // works. Home/End jump to the ends, matching the ARIA tabs pattern.
  const handleKeyDown = (event: KeyboardEvent<HTMLElement>, index: number) => {
    const lastIndex = tabs.length - 1
    let next: number | null = null

    if (event.key === "ArrowRight") next = index === lastIndex ? 0 : index + 1
    else if (event.key === "ArrowLeft") next = index === 0 ? lastIndex : index - 1
    else if (event.key === "Home") next = 0
    else if (event.key === "End") next = lastIndex

    if (next === null) return
    event.preventDefault()
    refs.current[next]?.focus()
    const target = tabs[next]
    if (target && !target.href) onSelect?.(target.id)
  }

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-1 rounded-lg border border-border bg-muted/30 p-1",
        className,
      )}
      role="tablist"
      aria-label={ariaLabel}
    >
      {tabs.map((tab, index) => {
        const selected = tab.id === active
        const content = (
          <>
            {/* The active pill is a single shared element that slides between
                tabs, so switching panels reads as one continuous movement
                instead of two independent color flips. */}
            {selected ? (
              <motion.span
                layoutId={indicatorLayoutId}
                className="absolute inset-0 rounded-md bg-background shadow-sm"
                transition={
                  reduceMotion
                    ? { duration: 0 }
                    : { type: "spring", stiffness: 400, damping: 32 }
                }
                aria-hidden
              />
            ) : null}
            <span className="relative z-10">{tab.label}</span>
            {typeof tab.count === "number" ? (
              <span
                className={cn(
                  "relative z-10 rounded px-1.5 py-0.5 text-[10px] font-semibold tabular-nums",
                  selected ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground",
                )}
              >
                {tab.count}
              </span>
            ) : null}
          </>
        )

        const classes = cn(
          "relative inline-flex items-center gap-1.5 rounded-md text-sm font-medium transition-colors",
          size === "sm" ? "px-2.5 py-1" : "px-3 py-1.5",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background",
          selected
            ? "text-foreground"
            : "text-muted-foreground hover:bg-background/60 hover:text-foreground",
        )

        // Only the selected tab stays in the tab order; arrow keys move between
        // them from there. This is the standard roving tabindex for tablists.
        const tabIndex = selected ? 0 : -1

        if (tab.href) {
          return (
            <Link
              key={tab.id}
              href={tab.href}
              role="tab"
              aria-selected={selected}
              tabIndex={tabIndex}
              ref={(node) => {
                refs.current[index] = node
              }}
              onKeyDown={(event) => handleKeyDown(event, index)}
              className={classes}
            >
              {content}
            </Link>
          )
        }

        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={selected}
            tabIndex={tabIndex}
            ref={(node) => {
              refs.current[index] = node
            }}
            onKeyDown={(event) => handleKeyDown(event, index)}
            onClick={() => onSelect?.(tab.id)}
            className={classes}
          >
            {content}
          </button>
        )
      })}
    </div>
  )
}
