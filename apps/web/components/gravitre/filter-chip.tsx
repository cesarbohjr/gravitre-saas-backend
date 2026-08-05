"use client"

import { motion, useReducedMotion } from "framer-motion"
import { useId } from "react"
import { type LucideIcon } from "lucide-react"
import { INTERACTION, MOTION, RADIUS, TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

/**
 * Toggleable filter pill. Extracted from marketplace/assets, which had the most
 * considered treatment of this control; agents / workflows / schedules each
 * hand-rolled their own raw <button> with different radii, colors and hover
 * states for the identical job.
 *
 * Uses aria-pressed (not role="tab") because filters are independent toggles
 * rather than a single-selection view switch — see SegmentedControl for that.
 */
export interface FilterChipProps {
  label: string
  active: boolean
  onClick: () => void
  icon?: LucideIcon
  /** Optional trailing count, e.g. number of matching rows. */
  count?: number
  className?: string
}

export function FilterChip({ label, active, onClick, icon: Icon, count, className }: FilterChipProps) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 border px-3 py-1.5 text-sm font-medium",
        RADIUS.control,
        INTERACTION,
        active
          ? "border-foreground bg-foreground text-background"
          : "border-border bg-background/60 text-muted-foreground hover:border-foreground/30 hover:text-foreground",
        className,
      )}
    >
      {Icon ? <Icon className="h-3.5 w-3.5" aria-hidden /> : null}
      {label}
      {typeof count === "number" ? (
        <span className={cn("tabular-nums text-xs", active ? "text-background/70" : "text-muted-foreground/70")}>
          {count}
        </span>
      ) : null}
    </button>
  )
}

export interface SegmentedOption<T extends string> {
  id: T
  label: string
  icon?: LucideIcon
}

/**
 * Single-select control for switching between mutually exclusive views.
 * The active background is one shared layout element, so selection slides
 * between options instead of blinking — matching the HubTabs indicator so the
 * two controls feel like the same system.
 */
export interface SegmentedControlProps<T extends string> {
  options: readonly SegmentedOption<T>[]
  value: T
  onChange: (value: T) => void
  /** Accessible name, e.g. "Filter by price". */
  ariaLabel: string
  className?: string
  /**
   * Render icons only, using each option's label as its accessible name.
   * For compact toolbars where the icons are self-evident (list vs board).
   */
  iconOnly?: boolean
}

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  ariaLabel,
  className,
  iconOnly = false,
}: SegmentedControlProps<T>) {
  const layoutId = useId()
  const reduceMotion = useReducedMotion()

  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className={cn("inline-flex items-center gap-0.5 border p-0.5", RADIUS.control, className)}
    >
      {options.map((option) => {
        const active = option.id === value
        const Icon = option.icon
        return (
          <button
            key={option.id}
            type="button"
            aria-pressed={active}
            // In icon-only mode the visible text is dropped, so the label has
            // to carry the accessible name instead.
            aria-label={iconOnly ? option.label : undefined}
            onClick={() => onChange(option.id)}
            className={cn(
              "relative inline-flex items-center justify-center gap-1.5 text-xs font-medium",
              iconOnly ? "p-2" : "px-3 py-1",
              RADIUS.control,
              INTERACTION,
              active ? "text-primary" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {active ? (
              <motion.span
                layoutId={layoutId}
                className={cn("absolute inset-0 bg-primary/10", RADIUS.control)}
                transition={reduceMotion ? { duration: 0 } : MOTION.spring}
                aria-hidden
              />
            ) : null}
            {Icon ? <Icon className="relative z-10 h-3.5 w-3.5" aria-hidden /> : null}
            {!iconOnly ? <span className="relative z-10">{option.label}</span> : null}
          </button>
        )
      })}
    </div>
  )
}

/**
 * Caps label that introduces a group of filters or a toolbar row.
 * Exists so the eyebrow tracking value is never retyped per page.
 */
export function FilterGroupLabel({ children, className }: { children: React.ReactNode; className?: string }) {
  return <span className={cn(TYPE.eyebrow, className)}>{children}</span>
}
