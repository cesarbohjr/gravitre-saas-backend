"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { useEffect, useMemo, useState } from "react"
import { Icon } from "@/lib/icons"
import { useViewMode } from "@/lib/view-mode-context"
import useSWR from "swr"
import { useOnboardingProgress } from "@/hooks/use-onboarding-progress"
import { useIsMobile } from "@/hooks/use-mobile"
import { useEnterpriseBranding } from "@/lib/enterprise-branding-context"
import { useAuth } from "@/lib/auth-context"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import {
  ADMIN_SIDEBAR_NAV,
  LITE_SIDEBAR_NAV,
  SIDEBAR_SECTION_COLORS,
  isSidebarItemActive,
} from "@/components/gravitre/sidebar-nav-config"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

const sectionColors = SIDEBAR_SECTION_COLORS

interface SidebarProps {
  isOpen?: boolean
  onClose?: () => void
  /** Desktop/tablet: show icon rail (false) vs full labels (true). */
  navExpanded?: boolean
  onToggleNavExpanded?: () => void
}

export function Sidebar({ isOpen, onClose, navExpanded = false, onToggleNavExpanded }: SidebarProps) {
  const pathname = usePathname()
  const [collapsedSections, setCollapsedSections] = useState<string[]>([])
  const isMobile = useIsMobile()
  const { isLite } = useViewMode()
  const { effectiveLogoUrl } = useEnterpriseBranding()
  const { user } = useAuth()
  const { progress, isComplete: onboardingComplete } = useOnboardingProgress()
  const { data: approvalsData } = useSWR<{ approvals?: Array<{ status?: string }> }>(
    user ? "/api/approvals" : null,
    apiFetcher,
    { revalidateOnFocus: false, dedupingInterval: 30_000 },
  )
  const pendingApprovals =
    approvalsData?.approvals?.filter((entry) => entry.status === "pending").length ?? 0

  const navigation = useMemo(() => {
    const base = isLite ? LITE_SIDEBAR_NAV : ADMIN_SIDEBAR_NAV
    return base.map((group) => ({
      ...group,
      items: group.items
        .filter((item) => {
          if (item.name === "Getting Started" && onboardingComplete) return false
          return true
        })
        .map((item) => {
          if (item.name === "Getting Started" && !onboardingComplete) {
            return { ...item, badge: `${progress}%` }
          }
          if (item.name === "Approvals" && pendingApprovals > 0) {
            return { ...item, badge: String(pendingApprovals) }
          }
          return item
        }),
    }))
  }, [isLite, onboardingComplete, progress, pendingApprovals])

  const toggleSection = (group: string) => {
    setCollapsedSections(prev =>
      prev.includes(group)
        ? prev.filter(g => g !== group)
        : [...prev, group]
    )
  }

  // Lock background scroll while the mobile drawer is open (no-op on desktop,
  // where isOpen stays false and the sidebar renders as a static rail).
  useEffect(() => {
    if (!isOpen) return
    const previous = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      document.body.style.overflow = previous
    }
  }, [isOpen])

  return (
    <TooltipProvider delayDuration={300}>
      {/* Mobile Overlay - Only show on mobile since sidebar is visible on tablet+ */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-background/80 backdrop-blur-sm md:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex h-full flex-col border-r border-sidebar-border bg-sidebar transition-all duration-300 ease-in-out",
          // Mobile: slide-out drawer
          "w-64",
          isOpen ? "translate-x-0" : "-translate-x-full",
          // Tablet+: pinned rail; width follows user expand preference
          "md:static md:z-auto md:translate-x-0",
          navExpanded ? "md:w-60" : "md:w-16",
        )}
      >
        {/* Logo */}
        <div className="flex h-16 items-center justify-between border-b border-sidebar-border px-3 md:px-2">
          <Link href="/" className="flex min-w-0 flex-1 items-center" onClick={onClose}>
            {effectiveLogoUrl ? (
              <>
                <div className={cn("hidden md:flex items-center justify-center h-16 w-16", navExpanded && "md:hidden")}>
                  <img
                    src={effectiveLogoUrl || "/placeholder.svg"}
                    alt="Workspace logo"
                    className="h-10 w-10 object-contain"
                    crossOrigin="anonymous"
                  />
                </div>
                <div className={cn(navExpanded ? "md:block" : "md:hidden")}>
                  <img
                    src={effectiveLogoUrl || "/placeholder.svg"}
                    alt="Workspace logo"
                    className="object-contain"
                    style={{ height: "40px", width: "auto", maxWidth: "180px" }}
                    crossOrigin="anonymous"
                  />
                </div>
              </>
            ) : (
              <>
                <div className={cn("hidden md:flex h-16 w-16 items-center justify-center", navExpanded && "md:hidden")}>
                  <img
                    src="/images/gravitre-icon-black.png"
                    alt="Gravitre"
                    className="h-16 w-16 object-contain dark:hidden"
                  />
                  <img
                    src="/images/gravitre-icon-white.png"
                    alt="Gravitre"
                    className="h-16 w-16 hidden object-contain dark:block"
                  />
                </div>
                <div className={cn(navExpanded ? "md:block" : "md:hidden")}>
                  <img
                    src="/images/gravitre-logo-black.png"
                    alt="Gravitre"
                    className="dark:hidden"
                    style={{ height: "40px", width: "auto" }}
                  />
                  <img
                    src="/images/gravitre-logo-white.png"
                    alt="Gravitre"
                    className="hidden dark:block"
                    style={{ height: "40px", width: "auto" }}
                  />
                </div>
              </>
            )}
          </Link>
          {onToggleNavExpanded ? (
            <Button
              variant="ghost"
              size="icon"
              className="hidden h-8 w-8 shrink-0 md:inline-flex hover:bg-sidebar-accent"
              onClick={onToggleNavExpanded}
              aria-label={navExpanded ? "Collapse navigation" : "Expand navigation"}
            >
              <Icon name={navExpanded ? "caretLeft" : "caretRight"} size="sm" />
            </Button>
          ) : null}
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 md:hidden hover:bg-sidebar-accent"
            onClick={onClose}
          >
            <Icon name="close" size="md" />
            <span className="sr-only">Close menu</span>
          </Button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto scrollbar-on-hover py-3 px-1.5 md:px-2 xl:px-2">
          {navigation.map((group, groupIndex) => {
            const colors = sectionColors[group.group]
            const isCollapsed = collapsedSections.includes(group.group)

            return (
              <div key={group.group} className="mb-0.5">
                {/* Section Divider */}
                {groupIndex > 0 && (
                  <div className="mx-2 mb-2 mt-2 h-px bg-sidebar-border" />
                )}

                {/* Section Header — labels when nav expanded (desktop) or mobile drawer */}
                <button
                  onClick={() => toggleSection(group.group)}
                  className={cn(
                    "hidden w-full items-center justify-between px-2 py-1 group rounded-md hover:bg-sidebar-accent/30 transition-colors",
                    navExpanded ? "md:flex" : "md:hidden",
                  )}
                >
                  <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground transition-colors group-hover:text-foreground">
                    {group.group}
                  </span>
                  <Icon
                    name="caretDown"
                    size="xs"
                    className={cn(
                      "text-muted-foreground/30 transition-transform duration-200",
                      isCollapsed && "-rotate-90",
                    )}
                  />
                </button>
                <div className="flex w-full items-center justify-between px-2 py-1 md:hidden">
                  <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                    {group.group}
                  </span>
                </div>

                {/* Section Items */}
                <div
                  className={cn(
                    "overflow-hidden transition-all duration-200",
                    isCollapsed && navExpanded ? "md:max-h-0 md:opacity-0" : "md:max-h-96 md:opacity-100",
                  )}
                >
                  <ul className="mt-0.5 space-y-px md:space-y-1 xl:space-y-px">
                    {group.items.map((item) => {
                      const isActive = isSidebarItemActive(pathname, item.href)
                      // Only wrap with a tooltip on the collapsed desktop rail, where
                      // labels are hidden and the tooltip adds value. On mobile (and the
                      // expanded rail) the Radix tooltip trigger intercepts the tap and
                      // blocks navigation — the original "menu opens, items dead" bug —
                      // so we render a bare Link there instead.
                      const showTooltip = !isMobile && !navExpanded
                      const linkEl = (
                              <Link
                                href={item.href}
                                onClick={onClose}
                                className={cn(
                                  "group relative flex items-center gap-2.5 rounded-md text-[13px] font-medium transition-all duration-150 px-2.5 py-1.5",
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
                                        "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground",
                                        navExpanded && "md:border-l-2 md:border-l-transparent md:-ml-px md:pl-[9px]",
                                      ),
                                )}
                              >
                                <Icon
                                  name={item.icon}
                                  size="md"
                                  emphasis={item.emphasis && isActive}
                                  className={cn(
                                    "shrink-0 transition-colors md:h-5 md:w-5",
                                    navExpanded && "md:h-4 md:w-4",
                                    isActive ? colors.activeIcon : "text-muted-foreground/70 group-hover:text-foreground",
                                  )}
                                />
                                <span className={cn("flex-1 truncate", navExpanded ? "md:inline" : "md:hidden")}>
                                  {item.name}
                                </span>
                                {item.badge && (
                                  <span
                                    className={cn(
                                      "rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide",
                                      navExpanded ? "md:inline" : "md:hidden",
                                      isActive
                                        ? "bg-primary/15 text-primary ring-1 ring-primary/20"
                                        : "bg-muted/60 text-muted-foreground/70",
                                    )}
                                  >
                                    {item.badge}
                                  </span>
                                )}
                              </Link>
                      )
                      return (
                        <li key={item.name}>
                          {showTooltip ? (
                            <Tooltip>
                              <TooltipTrigger asChild>{linkEl}</TooltipTrigger>
                              <TooltipContent
                                side="right"
                                className={cn(
                                  "max-w-xs text-xs hidden md:block",
                                  navExpanded && "md:hidden",
                                )}
                              >
                                <p className="font-medium">{item.name}</p>
                                {item.hint ? (
                                  <p className="mt-0.5 text-muted-foreground">{item.hint}</p>
                                ) : null}
                              </TooltipContent>
                            </Tooltip>
                          ) : (
                            linkEl
                          )}
                        </li>
                      )
                    })}
                  </ul>
                </div>
              </div>
            )
          })}
        </nav>

        {/* Footer */}
        <div className="border-t border-sidebar-border px-2 py-2.5 md:px-2">
          <div className={cn("flex items-center justify-between", navExpanded ? "md:justify-between" : "md:justify-center")}>
            <div className="flex items-center gap-2">
              <div className="flex h-6 w-6 items-center justify-center rounded-md bg-primary shadow-sm">
                <Icon name="shield" size="xs" className="text-primary-foreground" />
              </div>
              <div className={cn("flex flex-col", navExpanded ? "md:flex" : "md:hidden")}>
                <span className="text-[11px] font-medium text-foreground">Gravitre</span>
                <span className="text-[9px] text-muted-foreground/60">v1.2.0</span>
              </div>
            </div>
            <Tooltip>
              <TooltipTrigger asChild>
                <div
                  className={cn(
                    "flex h-2 w-2 cursor-help rounded-full bg-success",
                    navExpanded ? "md:flex" : "md:hidden",
                  )}
                />
              </TooltipTrigger>
              <TooltipContent side="top" className="text-xs">
                All systems operational
              </TooltipContent>
            </Tooltip>
          </div>
        </div>
      </aside>
    </TooltipProvider>
  )
}
