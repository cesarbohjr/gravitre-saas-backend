import type { ButtonHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react"

import { cn } from "@/lib/cn"

/**
 * Extension primitives.
 *
 * These mirror the main app's token usage and sizing rather than importing from
 * it: apps/web is a separate project with no workspace link, and its shadcn
 * components pull in Radix, which is far too heavy to inject into a host page.
 * Every colour below is a semantic token, so light/dark come for free.
 */

const FOCUS =
  "outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card"

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger"
  size?: "sm" | "md"
  block?: boolean
}

export function Button({
  variant = "primary",
  size = "md",
  block,
  className,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded-md font-medium",
        "transition-[background-color,border-color,color,box-shadow] duration-150",
        "disabled:pointer-events-none disabled:opacity-50",
        FOCUS,
        size === "sm" ? "h-7 px-2.5 text-xs" : "h-8 px-3 text-[13px]",
        block && "w-full",
        variant === "primary" &&
          "bg-primary text-primary-foreground shadow-elevation-1 hover:brightness-110",
        variant === "secondary" &&
          "border border-border bg-card text-foreground hover:bg-secondary",
        variant === "ghost" && "text-muted-foreground hover:bg-secondary hover:text-foreground",
        variant === "danger" &&
          "border border-destructive/30 bg-transparent text-destructive hover:bg-destructive/10",
        className,
      )}
    >
      {children}
    </button>
  )
}

export function Card({
  children,
  className,
  elevation = 4,
}: {
  children: ReactNode
  className?: string
  elevation?: 1 | 2 | 3 | 4
}) {
  return (
    <div
      className={cn(
        // A real boundary plus the app's own elevation scale, so the overlay
        // reads as floating above the host page rather than pasted into it
        // (Part B.2).
        "rounded-xl border border-border bg-card text-card-foreground",
        elevation === 1 && "shadow-elevation-1",
        elevation === 2 && "shadow-elevation-2",
        elevation === 3 && "shadow-elevation-3",
        elevation === 4 && "shadow-elevation-4",
        className,
      )}
    >
      {children}
    </div>
  )
}

/** Small uppercase section label — the app's grouping device. */
export function SectionLabel({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground",
        className,
      )}
    >
      {children}
    </div>
  )
}

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode
  tone?: "neutral" | "success" | "warning" | "info" | "primary"
  className?: string
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium leading-4",
        tone === "neutral" && "bg-secondary text-secondary-foreground",
        tone === "success" && "bg-success/12 text-success",
        tone === "warning" && "bg-warning/15 text-warning",
        tone === "info" && "bg-info/12 text-info",
        tone === "primary" && "bg-primary/12 text-primary",
        className,
      )}
    >
      {children}
    </span>
  )
}

/**
 * Label/value pair. Values wrap rather than truncate — an email or company you
 * cannot read defeats the point of enrichment.
 */
export function Field({
  label,
  value,
  mono,
}: {
  label: string
  value: ReactNode
  mono?: boolean
}) {
  return (
    <div className="flex items-baseline gap-3 py-1">
      <dt className="w-16 shrink-0 text-[11px] text-muted-foreground">{label}</dt>
      <dd
        className={cn(
          "min-w-0 flex-1 break-words text-[13px] leading-relaxed text-foreground",
          mono && "font-mono text-[11px]",
        )}
      >
        {value}
      </dd>
    </div>
  )
}

export function Textarea({
  className,
  ...rest
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...rest}
      className={cn(
        "w-full resize-none rounded-md border border-border bg-input px-2.5 py-2",
        "text-[13px] leading-relaxed text-foreground placeholder:text-muted-foreground",
        FOCUS,
        className,
      )}
    />
  )
}

export function Input({
  className,
  ...rest
}: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...rest}
      className={cn(
        "h-8 w-full rounded-md border border-border bg-input px-2.5",
        "text-[13px] text-foreground placeholder:text-muted-foreground",
        FOCUS,
        className,
      )}
    />
  )
}

export function Divider({ className }: { className?: string }) {
  return <div role="presentation" className={cn("h-px bg-border", className)} />
}

/** Inline status line used for errors and transient notices. */
export function Notice({
  tone = "muted",
  children,
}: {
  tone?: "muted" | "danger"
  children: ReactNode
}) {
  return (
    <p
      className={cn(
        "text-[12px] leading-relaxed",
        tone === "muted" && "text-muted-foreground",
        tone === "danger" && "text-destructive",
      )}
      role={tone === "danger" ? "alert" : undefined}
    >
      {children}
    </p>
  )
}
