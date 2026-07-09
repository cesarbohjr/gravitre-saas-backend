"use client"

import Link from "next/link"
import { cn } from "@/lib/utils"
import { Icon, type IconName } from "@/lib/icons"
import type { SIDEBAR_SECTION_COLORS } from "./sidebar-nav-config"

type SectionColors = (typeof SIDEBAR_SECTION_COLORS)[keyof typeof SIDEBAR_SECTION_COLORS]

export interface SidebarNavLinkProps {
  href: string
  name: string
  icon: IconName
  isActive: boolean
  navExpanded: boolean
  showTooltip: boolean
  badge?: string
  emphasis?: boolean
  hint?: string
  colors: SectionColors
  onNavigate?: () => void
}

export function SidebarNavLink({
  href,
  name,
  icon,
  isActive,
  navExpanded,
  showTooltip,
  badge,
  emphasis,
  hint,
  colors,
  onNavigate,
}: SidebarNavLinkProps) {
  const tooltip = showTooltip ? (hint ? `${name} — ${hint}` : name) : undefined

  return (
    <Link
      href={href}
      title={tooltip}
      aria-label={showTooltip ? name : undefined}
      data-testid={`sidebar-link-${sidebarLinkTestId(name)}`}
      onClick={() => onNavigate?.()}
      className={cn(
        "group relative z-10 flex w-full items-center gap-2.5 rounded-md text-[13px] font-medium transition-colors duration-150 px-2.5 py-1.5",
        navExpanded
          ? "md:justify-start md:px-2.5 md:py-1.5"
          : "md:justify-center md:px-0 md:py-2.5",
        isActive
          ? cn(
              colors.activeBg,
              "text-foreground",
              navExpanded && "md:border-l-2 md:-ml-px md:pl-[9px]",
              colors.activeBorder,
            )
          : cn(
              "text-muted-foreground/70 hover:text-foreground hover:bg-sidebar-accent/50",
              navExpanded && "md:border-l-2 md:border-l-transparent md:-ml-px md:pl-[9px]",
            ),
      )}
    >
      <Icon
        name={icon}
        size="md"
        emphasis={emphasis && isActive}
        className={cn(
          "shrink-0 transition-colors md:h-5 md:w-5",
          navExpanded && "md:h-4 md:w-4",
          isActive ? colors.activeIcon : "text-muted-foreground/40 group-hover:text-muted-foreground/70",
        )}
      />
      <span className={cn("min-w-0 flex-1 truncate", navExpanded ? "md:inline" : "md:hidden")}>{name}</span>
      {badge ? (
        <span
          className={cn(
            "rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide",
            navExpanded ? "md:inline" : "md:hidden",
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
