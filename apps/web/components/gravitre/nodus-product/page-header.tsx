"use client"

import type { ReactNode } from "react"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import { TYPE } from "@/lib/design-system"
import { resolvePageFamily, type PageFamily } from "@/lib/page-family"

export type PageHeaderFamily = Exclude<PageFamily, "immersive">

/**
 * Page intro by job (G-STRUCT A1), resolved from the route unless a page passes
 * `family`:
 *  - operating — open intro on the canvas: large title, live status line, primary
 *    actions; no divider, the attention content directly follows.
 *  - expert — a dense tool band: compact title, inline meta and tools, tabs flush
 *    below; the working area starts immediately.
 *  - standard — the operating rhythm at a quieter scale.
 */
export function GravitrePageHeader({
  title,
  description,
  icon,
  actions,
  children,
  className,
  eyebrow,
  status,
  family,
}: {
  title: string
  description?: string
  icon?: ReactNode
  actions?: ReactNode
  children?: ReactNode
  className?: string
  eyebrow?: string
  /** Live state line under the title (operating) or beside it (expert). */
  status?: ReactNode
  family?: PageHeaderFamily
}) {
  const pathname = usePathname() ?? ""
  const routeFamily = resolvePageFamily(pathname)
  const resolved: PageHeaderFamily = family ?? (routeFamily === "immersive" ? "standard" : routeFamily)

  if (resolved === "expert") {
    return (
      <div
        data-page-header-family="expert"
        className={cn(
          "min-w-0 border-b border-[color:var(--g-border-default)] bg-[color:var(--g-rail-bg)] px-[var(--np-page-pad-sm)] pt-3 sm:px-[var(--np-page-pad)]",
          children ? "pb-0" : "pb-3",
          className,
        )}
      >
        <div className="flex min-w-0 flex-col justify-between gap-2.5 pb-2.5 sm:flex-row sm:items-center">
          <div className="flex min-w-0 items-center gap-2.5">
            {icon ? (
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[9px] border border-[color:var(--g-border-default)] bg-background text-[color:var(--g-brand)]">
                {icon}
              </div>
            ) : null}
            <div className="min-w-0">
              {eyebrow ? <p className={cn(TYPE.eyebrow, "leading-none")}>{eyebrow}</p> : null}
              <div className="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-0.5">
                <h1 className="font-sans text-[17px] font-semibold tracking-[-0.01em] text-[color:var(--g-text-primary)]">
                  {title}
                </h1>
                {description ? (
                  <p className="hidden min-w-0 max-w-2xl truncate text-[13px] text-[color:var(--g-text-muted)] lg:block">
                    {description}
                  </p>
                ) : null}
              </div>
              {status ? <div className="mt-0.5 text-xs text-[color:var(--g-text-muted)]">{status}</div> : null}
            </div>
          </div>
          {actions ? (
            <div className="flex w-full shrink-0 flex-wrap items-center gap-2 sm:w-auto sm:justify-end">{actions}</div>
          ) : null}
        </div>
        {children}
      </div>
    )
  }

  const operating = resolved === "operating"
  return (
    <div
      data-page-header-family={resolved}
      className={cn(
        "min-w-0 px-[var(--np-page-pad-sm)] sm:px-[var(--np-page-pad)]",
        operating ? "pb-3 pt-5 sm:pb-4 sm:pt-7" : "pb-3 pt-4 sm:pt-6",
        className,
      )}
    >
      <div className="flex min-w-0 flex-col justify-between gap-3 lg:flex-row lg:items-end">
        <div className="flex min-w-0 flex-1 items-start gap-3">
          {icon ? (
            <div
              className={cn(
                "mt-0.5 flex shrink-0 items-center justify-center rounded-[10px] bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)]",
                operating ? "h-10 w-10" : "h-9 w-9",
              )}
            >
              {icon}
            </div>
          ) : null}
          <div className="min-w-0 space-y-1">
            {eyebrow ? <p className={TYPE.eyebrow}>{eyebrow}</p> : null}
            <h1
              className={cn(
                "font-sans font-semibold text-[color:var(--g-text-primary)]",
                operating
                  ? "text-[24px] leading-[1.15] tracking-[-0.02em] sm:text-[28px]"
                  : "text-xl tracking-tight sm:text-2xl",
              )}
            >
              {title}
            </h1>
            {description ? <p className={cn(TYPE.pageLead, "max-w-2xl")}>{description}</p> : null}
            {status ? <div className="pt-0.5 text-[13px] text-[color:var(--g-text-muted)]">{status}</div> : null}
          </div>
        </div>
        {actions ? (
          <div className="flex w-full shrink-0 flex-wrap items-center gap-2 lg:w-auto lg:justify-end">{actions}</div>
        ) : null}
      </div>
      {children ? <div className="mt-3">{children}</div> : null}
    </div>
  )
}

/** Pulsing live dot + text for operating status lines. */
export function LiveStatus({ children, tone = "live" }: { children: ReactNode; tone?: "live" | "idle" | "attention" }) {
  return (
    <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-0.5">
      <span className="relative flex h-2 w-2" aria-hidden>
        {tone === "live" ? (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[color:var(--g-brand)] opacity-40 motion-reduce:animate-none" />
        ) : null}
        <span
          className={cn(
            "relative inline-flex h-2 w-2 rounded-full",
            tone === "live" && "bg-[color:var(--g-brand)]",
            tone === "idle" && "bg-muted-foreground/50",
            tone === "attention" && "bg-warning",
          )}
        />
      </span>
      {children}
    </span>
  )
}
