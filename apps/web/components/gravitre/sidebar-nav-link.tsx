"use client"

import Link from "next/link"
import { cn } from "@/lib/utils"
import { Icon, type IconName } from "@/lib/icons"
import type { SIDEBAR_SECTION_COLORS } from "./sidebar-nav-config"
import { clearStalePointerLocks } from "./pointer-events-guard"

type SectionColors = (typeof SIDEBAR_SECTION_COLORS)[keyof typeof SIDEBAR_SECTION_COLORS]

export interface SidebarNavLinkProps {
  href: string
  name: string
  icon: IconName
  isActive: boolean
  badge?: string
  emphasis?: boolean
  colors: SectionColors
  onNavigate?: () => void
}

/**
 * Soft App Router navigation via next/link so the persistent AppShell (sidebar)
 * stays mounted. If the URL has not changed shortly after click (historical
 * soft-nav stall), fall back to a hard navigation.
 */
export function SidebarNavLink({
  href,
  name,
  icon,
  isActive,
  badge,
  emphasis,
  colors,
  onNavigate,
}: SidebarNavLinkProps) {
  return (
    <Link
      href={href}
      prefetch
      data-testid={`sidebar-link-${sidebarLinkTestId(name)}`}
      onClick={(event) => {
        clearStalePointerLocks()
        onNavigate?.()

        if (
          event.defaultPrevented ||
          event.metaKey ||
          event.ctrlKey ||
          event.shiftKey ||
          event.altKey ||
          event.button !== 0
        ) {
          return
        }

        const from = typeof window !== "undefined" ? window.location.pathname : ""
        const targetPath = href.split("?")[0] ?? href
        window.setTimeout(() => {
          if (typeof window === "undefined") return
          const current = window.location.pathname
          if (current === from && current !== targetPath) {
            window.location.assign(href)
          }
        }, 400)
      }}
      className={cn(
        "group relative z-10 flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] font-medium transition-colors duration-150",
        isActive
          ? cn(colors.activeBg, "border-l-2 -ml-px pl-[9px] text-foreground", colors.activeBorder)
          : "border-l-2 border-l-transparent -ml-px pl-[9px] text-muted-foreground/70 hover:bg-sidebar-accent/50 hover:text-foreground",
      )}
    >
      <Icon
        name={icon}
        size="md"
        emphasis={emphasis && isActive}
        className={cn(
          "h-4 w-4 shrink-0 transition-colors",
          isActive ? colors.activeIcon : "text-muted-foreground/40 group-hover:text-muted-foreground/70",
        )}
      />
      <span className="min-w-0 flex-1 truncate">{name}</span>
      {badge ? (
        <span
          className={cn(
            "rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide",
            isActive
              ? "bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/20"
              : "bg-muted/60 text-muted-foreground/70",
          )}
        >
          {badge}
        </span>
      ) : null}
    </Link>
  )
}

function sidebarLinkTestId(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
}
