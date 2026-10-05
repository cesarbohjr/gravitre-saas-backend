"use client"

import React, { useEffect, useState } from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { useIsMobile } from "@/hooks/use-mobile"
import { TYPE } from "@/lib/design-system"
import {
  ADMIN_ONLY_SETTINGS_SECTIONS,
  SETTINGS_SECTIONS,
  SETTINGS_TIER_LABELS,
  WIDE_SETTINGS_SECTIONS,
  settingsSectionsForTier,
  type SettingsSectionId,
  type SettingsTier,
} from "@/lib/settings-sections"

const TIER_ORDER: SettingsTier[] = ["personal", "organization", "admin"]

interface SettingsShellProps {
  activeSection: SettingsSectionId
  onSectionChange?: (section: SettingsSectionId) => void
  isAdmin: boolean
  mobileMenuOpen?: boolean
  onMobileMenuOpenChange?: (open: boolean) => void
  /** Hide the default desktop title block (page supplies its own hero). */
  hideHeader?: boolean
  children: React.ReactNode
}

export function SettingsShell({
  activeSection,
  onSectionChange,
  isAdmin,
  mobileMenuOpen,
  onMobileMenuOpenChange,
  hideHeader,
  children,
}: SettingsShellProps) {
  const [localMenuOpen, setLocalMenuOpen] = useState(false)
  const isCompact = useIsMobile(1024)
  const menuOpen = mobileMenuOpen ?? localMenuOpen
  const setMenuOpen = onMobileMenuOpenChange ?? setLocalMenuOpen
  useEffect(() => {
    if (!isCompact && menuOpen) setMenuOpen(false)
  }, [isCompact, menuOpen, setMenuOpen])
  const activeMeta = SETTINGS_SECTIONS.find((section) => section.id === activeSection)
  const showHeader = !hideHeader
  const wide = WIDE_SETTINGS_SECTIONS.has(activeSection)

  const tiers = TIER_ORDER.filter((tier) => {
    if (tier === "admin" && !isAdmin) return false
    return settingsSectionsForTier(tier, isAdmin).length > 0
  })


  return (
    <Sheet open={isCompact && menuOpen} onOpenChange={setMenuOpen}>
    <div className="relative flex h-full min-h-0 flex-col bg-[color:var(--g-surface-1)] lg:flex-row">
      <div className="sticky top-0 z-20 flex items-start justify-between gap-3 border-b border-divide bg-[color:var(--g-surface-1)] px-4 py-3 lg:hidden">
        <div className="min-w-0 flex-1">
          <p className="mb-1 text-xs text-muted-foreground">Settings</p>
          {!hideHeader && <>
            <h1 className={cn(TYPE.pageTitle, "[overflow-wrap:anywhere]")}>{activeMeta?.title}</h1>
            <p className={cn(TYPE.pageLead, "mt-1")}>{activeMeta?.description}</p>
          </>}
        </div>
        <SheetTrigger asChild>
          <Button variant="outline" className="min-h-11 shrink-0 gap-2" aria-label="Choose settings section">
            {activeMeta ? <activeMeta.icon className="h-4 w-4" /> : null} Sections
          </Button>
        </SheetTrigger>
      </div>
      <SheetContent side="left" className="w-[min(92vw,360px)] overflow-y-auto p-0 sm:max-w-[360px] data-[state=open]:duration-200 [&>button]:size-11">
        <SheetHeader className="pr-14">
          <SheetTitle className="font-sans">Settings sections</SheetTitle>
          <SheetDescription>Choose the settings you want to manage.</SheetDescription>
        </SheetHeader>
        <nav aria-label="Settings section sheet" className="space-y-4 px-4 pb-6">
          {tiers.map((tier) => <div key={tier}>
            <p className={cn(TYPE.eyebrow, "mb-1.5 px-3")}>{SETTINGS_TIER_LABELS[tier]}</p>
            <div className="space-y-1">
              {settingsSectionsForTier(tier, isAdmin).map((section) => <SettingsNavItem key={section.id}
                section={section} activeSection={activeSection} onSectionChange={onSectionChange}
                onNavigate={() => setMenuOpen(false)} />)}
            </div>
          </div>)}
        </nav>
      </SheetContent>

      <aside className="relative z-30 hidden min-h-full w-64 shrink-0 self-stretch border-r border-divide bg-[color:var(--g-surface-1)] p-4 lg:block">
        <nav className="space-y-4" aria-label="Settings sections">
          {tiers.map((tier) => {
            const sections = settingsSectionsForTier(tier, isAdmin)
            return (
              <div key={tier}>
                <p className={cn(TYPE.eyebrow, "mb-1.5 px-3")}>{SETTINGS_TIER_LABELS[tier]}</p>
                <div className="space-y-1">
                  {sections.map((section) => (
                    <SettingsNavItem
                      key={section.id}
                      section={section}
                      activeSection={activeSection}
                      onSectionChange={onSectionChange}
                    />
                  ))}
                </div>
              </div>
            )
          })}
        </nav>
      </aside>

      <div className="relative z-10 min-w-0 flex-1 overflow-auto bg-[color:var(--g-canvas)]">
        <div
          className={cn(
            "mx-auto",
            hideHeader
              ? cn(wide ? "max-w-5xl" : "max-w-2xl lg:mx-0")
              : cn(
                  "px-[var(--np-page-pad-sm)] py-4 sm:px-[var(--np-page-pad)] lg:py-6",
                  wide ? "max-w-5xl" : "max-w-2xl lg:mx-0",
                ),
          )}
        >
          {showHeader ? (
            <div className="mb-6 hidden lg:block">
              <h1 className={cn(TYPE.pageTitle, "mb-1")}>{activeMeta?.title}</h1>
              <p className={TYPE.pageLead}>{activeMeta?.description}</p>
            </div>
          ) : null}
          {children}
        </div>
      </div>
    </div>
    </Sheet>
  )
}

function SettingsNavItem({
  section,
  activeSection,
  onSectionChange,
  onNavigate,
}: {
  section: (typeof SETTINGS_SECTIONS)[number]
  activeSection: SettingsSectionId
  onSectionChange?: (section: SettingsSectionId) => void
  onNavigate?: () => void
}) {
  const isActive = activeSection === section.id
  const className = cn(
    "flex min-h-11 w-full items-center gap-3 rounded-[var(--np-radius-md)] px-3 py-2 text-left text-sm transition-colors motion-reduce:transition-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--g-brand)]",
    isActive
      ? "bg-[color:var(--g-brand-soft)] font-medium text-[color:var(--g-brand-active)] dark:text-[color:var(--g-brand)]"
      : "text-[color:var(--g-text-muted)] hover:bg-[color:var(--g-surface-2)] hover:text-[color:var(--g-text-primary)]",
  )

  if (section.href) {
    return (
      <Link href={section.href} onClick={onNavigate} className={className} aria-current={isActive ? "page" : undefined}>
        <section.icon className="h-4 w-4 shrink-0" />
        <span className="min-w-0 [overflow-wrap:anywhere]">{section.title}</span>
      </Link>
    )
  }

  return (
    <button type="button" aria-current={isActive ? "page" : undefined} onClick={() => { onNavigate?.(); onSectionChange?.(section.id) }} className={className}>
      <section.icon className="h-4 w-4 shrink-0" />
      <span className="min-w-0 [overflow-wrap:anywhere]">{section.title}</span>
    </button>
  )
}

export function canAccessSettingsSection(section: SettingsSectionId, isAdmin: boolean): boolean {
  if (!ADMIN_ONLY_SETTINGS_SECTIONS.has(section)) return true
  return isAdmin
}
