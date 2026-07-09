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

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const pathname = usePathname()
  const isMobile = useIsMobile()
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
      badge={item.badge}
      emphasis={item.emphasis}
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
          // min-h-0 is required so the flex/grid child can shrink and the nav can scroll.
          "flex h-full min-h-0 w-60 shrink-0 flex-col overflow-hidden border-r border-sidebar-border bg-sidebar transition-transform duration-300 ease-in-out",
          // Desktop/tablet: stay in document flow so main content cannot stack over nav hits.
          "md:relative md:z-30 md:translate-x-0 md:visible md:pointer-events-auto",
          // Mobile: off-canvas drawer only below md breakpoint.
          "max-md:fixed max-md:inset-y-0 max-md:left-0 max-md:z-50",
          isOpen
            ? "max-md:translate-x-0 max-md:pointer-events-auto"
            : "max-md:-translate-x-full max-md:invisible max-md:pointer-events-none",
        )}
        aria-hidden={!isOpen && isMobile ? true : undefined}
      >
        <div className="flex h-16 shrink-0 items-center justify-between border-b border-sidebar-border px-3">
          <Link href="/" className="flex min-w-0 flex-1 items-center" onClick={handleNavClick}>
            {effectiveLogoUrl ? (
              <img
                src={effectiveLogoUrl}
                alt="Workspace logo"
                className="object-contain"
                style={{ height: "40px", width: "auto", maxWidth: "180px" }}
                crossOrigin="anonymous"
              />
            ) : (
              <>
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
              </>
            )}
          </Link>
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

        <nav
          className="relative z-10 min-h-0 flex-1 overflow-x-hidden overflow-y-auto overscroll-contain py-3 px-2 [scrollbar-gutter:stable]"
          aria-label="Main"
        >
          {navigation.map((group, groupIndex) => {
            const colors = SIDEBAR_SECTION_COLORS[group.group]
            const isCollapsed = collapsedSections.includes(group.group)

            return (
              <section key={group.group} className="mb-0.5">
                {groupIndex > 0 ? <div className="mx-2 mb-2 mt-1.5 h-px bg-border/40" aria-hidden /> : null}

                <div className="mb-0.5 flex items-center justify-between px-2 py-1">
                  <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/50">
                    {group.group}
                  </span>
                  <button
                    type="button"
                    aria-expanded={!isCollapsed}
                    aria-label={
                      isCollapsed ? `Expand ${group.group} section` : `Collapse ${group.group} section`
                    }
                    onClick={() => toggleSection(group.group)}
                    className="rounded p-1 hover:bg-sidebar-accent/30"
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
                </div>

                {!isCollapsed ? (
                  <ul className="space-y-px">
                    {group.items.map((item) => (
                      <li key={`${item.href}-${item.name}`}>{renderItem(item, colors)}</li>
                    ))}
                  </ul>
                ) : null}
              </section>
            )
          })}
        </nav>

        <div className="shrink-0 border-t border-sidebar-border px-2 py-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="flex h-6 w-6 items-center justify-center rounded-md bg-gradient-to-br from-emerald-500 to-emerald-600 shadow-sm">
                <Icon name="shield" size="xs" className="text-white" />
              </div>
              <div className="flex flex-col">
                <span className="text-[11px] font-medium text-foreground">Gravitre</span>
                <span className="text-[9px] text-muted-foreground/60">v1.2.0</span>
              </div>
            </div>
            <span
              title="All systems operational"
              className="h-2 w-2 cursor-help rounded-full bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.5)]"
            />
          </div>
        </div>
      </aside>
    </>
  )
}
