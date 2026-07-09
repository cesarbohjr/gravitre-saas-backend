"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
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
  const router = useRouter()

  return (
    <Link
      href={href}
      data-testid={`sidebar-link-${sidebarLinkTestId(name)}`}
      onClick={(event) => {
        // Clear stale Radix scroll-locks before the browser resolves the click target.
        clearStalePointerLocks()
        onNavigate?.()

        // If a leftover overlay still intercepts the native Link navigation,
        // force a client transition. Skip modified clicks (new tab, etc.).
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

        // Soft insurance: after a tick, if URL didn't change toward href, push.
        const before = window.location.pathname + window.location.search + window.location.hash
        window.setTimeout(() => {
          const after = window.location.pathname + window.location.search + window.location.hash
          if (after === before) {
            const target = new URL(href, window.location.origin)
            const targetKey = target.pathname + target.search + target.hash
            if (targetKey !== after) {
              clearStalePointerLocks()
              router.push(href)
            }
          }
        }, 250)
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
