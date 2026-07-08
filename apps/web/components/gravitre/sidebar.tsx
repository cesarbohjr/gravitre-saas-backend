"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { useMemo, useState, useEffect, useCallback } from "react"
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
  type SidebarNavGroup,
  type SidebarNavItem,
} from "./sidebar-nav-config"
import { SidebarNavLink } from "./sidebar-nav-link"

interface SidebarProps {
  isOpen?: boolean
  onClose?: () => void
  navExpanded?: boolean
  onToggleNavExpanded?: () => void
}

function buildNavigation(
  groups: SidebarNavGroup[],
  options: {
    onboardingComplete: boolean
    progress: number
    pendingApprovals: number
  },
): SidebarNavGroup[] {
  const { onboardingComplete, progress, pendingApprovals } = options

  return groups.map((group) => ({
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
}

export function Sidebar({ isOpen, onClose, navExpanded = false, onToggleNavExpanded }: SidebarProps) {
  const pathname = usePathname()
  const isMobile = useIsMobile()
  const showNavTooltip = !isMobile && !navExpanded
  const [collapsedSections, setCollapsedSections] = useState<string[]>([])
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

  const navigation = useMemo(
    () =>
      buildNavigation(isLite ? LITE_SIDEBAR_NAV : ADMIN_SIDEBAR_NAV, {
        onboardingComplete,
        progress,
        pendingApprovals,
      }),
    [isLite, onboardingComplete, progress, pendingApprovals],
  )

  const toggleSection = (group: string) => {
    setCollapsedSections((prev) =>
      prev.includes(group) ? prev.filter((g) => g !== group) : [...prev, group],
    )
  }

  // Close the mobile drawer after route changes (native Link navigation).
  useEffect(() => {
    if (!isMobile || !isOpen) return
    onClose?.()
  }, [pathname, isMobile, isOpen, onClose])

  const handleNavClick = useCallback(() => {
    if (isMobile) onClose?.()
  }, [isMobile, onClose])

  const renderItem = (item: SidebarNavItem, colors: (typeof SIDEBAR_SECTION_COLORS)[keyof typeof SIDEBAR_SECTION_COLORS]) => (
    <SidebarNavLink
      key={`${item.href}-${item.name}`}
      href={item.href}
      name={item.name}
      icon={item.icon}
      isActive={isSidebarItemActive(pathname, item.href)}
      navExpanded={navExpanded}
      showTooltip={showNavTooltip}
      badge={item.badge}
      emphasis={item.emphasis}
      hint={item.hint}
      colors={colors}
      onNavigate={handleNavClick}
    />
  )

  return (
    <>
      {isOpen ? (
        <button
          type="button"
          aria-label="Close navigation menu"
          className="fixed inset-0 z-40 bg-background/80 backdrop-blur-sm md:hidden"
          onClick={onClose}
        />
      ) : null}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex h-full shrink-0 flex-col border-r border-sidebar-border bg-sidebar transition-[transform,width] duration-300 ease-in-out",
          "w-64",
          isOpen ? "translate-x-0 max-md:pointer-events-auto" : "-translate-x-full max-md:invisible max-md:pointer-events-none",
          "md:pointer-events-auto md:static md:z-auto md:translate-x-0 md:flex-shrink-0 md:visible",
          navExpanded ? "md:w-60" : "md:w-16",
        )}
        aria-hidden={!isOpen && isMobile ? true : undefined}
      >
        <div className="flex h-16 shrink-0 items-center justify-between border-b border-sidebar-border px-3 md:px-2">
          <Link href="/" className="flex min-w-0 flex-1 items-center" onClick={handleNavClick}>
            {effectiveLogoUrl ? (
              <>
                <div className={cn("hidden md:flex h-10 w-10 items-center justify-center", navExpanded && "md:hidden")}>
                  <img
                    src={effectiveLogoUrl}
                    alt="Workspace logo"
                    className="h-10 w-10 object-contain"
                    crossOrigin="anonymous"
                  />
                </div>
                <div className={cn(navExpanded ? "md:block" : "md:hidden")}>
                  <img
                    src={effectiveLogoUrl}
                    alt="Workspace logo"
                    className="object-contain"
                    style={{ height: "40px", width: "auto", maxWidth: "180px" }}
                    crossOrigin="anonymous"
                  />
                </div>
              </>
            ) : (
              <>
                <div className={cn("hidden md:flex h-10 w-10 items-center justify-center", navExpanded && "md:hidden")}>
                  <img src="/images/gravitre-icon-black.png" alt="Gravitre" className="h-10 w-10 object-contain dark:hidden" />
                  <img
                    src="/images/gravitre-icon-white.png"
                    alt="Gravitre"
                    className="hidden h-10 w-10 object-contain dark:block"
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

        <nav className="min-h-0 flex-1 overflow-y-auto overscroll-contain py-3 px-1.5 md:px-2" aria-label="Main">
          {navigation.map((group, groupIndex) => {
            const colors = SIDEBAR_SECTION_COLORS[group.group]
            const isCollapsed = collapsedSections.includes(group.group)
            const showSectionItems = !(isCollapsed && navExpanded)

            return (
              <section key={group.group} className="mb-0.5">
                {groupIndex > 0 ? <div className="mx-2 mb-2 mt-1.5 h-px bg-border/40" aria-hidden /> : null}

                <div
                  className={cn(
                    "mb-0.5 flex items-center justify-between px-2 py-1",
                    navExpanded ? "md:flex" : "md:hidden",
                  )}
                >
                  <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/50">
                    {group.group}
                  </span>
                  {navExpanded ? (
                    <button
                      type="button"
                      aria-expanded={!isCollapsed}
                      aria-label={
                        isCollapsed ? `Expand ${group.group} section` : `Collapse ${group.group} section`
                      }
                      onClick={() => toggleSection(group.group)}
                      className="hidden rounded p-1 hover:bg-sidebar-accent/30 md:inline-flex"
                    >
                      <Icon
                        name="caretDown"
                        size="xs"
                        className={cn(
                          "text-muted-foreground/30 transition-transform duration-200",
                          isCollapsed && "-rotate-90",
                        )}
                      />
                    </button>
                  ) : null}
                </div>

                {showSectionItems ? (
                  <ul className="space-y-px md:space-y-1 xl:space-y-px">
                    {group.items.map((item) => (
                      <li key={`${item.href}-${item.name}`}>{renderItem(item, colors)}</li>
                    ))}
                  </ul>
                ) : null}
              </section>
            )
          })}
        </nav>

        <div className="shrink-0 border-t border-sidebar-border px-2 py-2.5 md:px-2">
          <div className={cn("flex items-center justify-between", navExpanded ? "md:justify-between" : "md:justify-center")}>
            <div className="flex items-center gap-2">
              <div className="flex h-6 w-6 items-center justify-center rounded-md bg-gradient-to-br from-emerald-500 to-emerald-600 shadow-sm">
                <Icon name="shield" size="xs" className="text-white" />
              </div>
              <div className={cn("flex flex-col", navExpanded ? "md:flex" : "md:hidden")}>
                <span className="text-[11px] font-medium text-foreground">Gravitre</span>
                <span className="text-[9px] text-muted-foreground/60">v1.2.0</span>
              </div>
            </div>
            <span
              title="All systems operational"
              className={cn(
                "h-2 w-2 cursor-help rounded-full bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.5)]",
                navExpanded ? "md:inline-block" : "md:hidden",
              )}
            />
          </div>
        </div>
      </aside>
    </>
  )
}
