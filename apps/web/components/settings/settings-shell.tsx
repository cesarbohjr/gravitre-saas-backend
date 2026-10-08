"use client"

import React, { useEffect, useId, useState } from "react"
import Link from "next/link"
import { Lock, Search, ShieldCheck, User, Users, type LucideIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { useIsMobile } from "@/hooks/use-mobile"
import { TYPE } from "@/lib/design-system"
import {
  ADMIN_ONLY_SETTINGS_SECTIONS,
  SETTINGS_SECTIONS,
  SETTINGS_TIER_LABELS,
  SETTINGS_TIER_SCOPE,
  WIDE_SETTINGS_SECTIONS,
  settingsSectionsForTier,
  type SettingsSectionId,
  type SettingsTier,
} from "@/lib/settings-sections"

const TIER_ORDER: SettingsTier[] = ["personal", "organization", "admin"]

const TIER_ICON: Record<SettingsTier, LucideIcon> = {
  personal: User,
  organization: Users,
  admin: ShieldCheck,
}

function ScopeLine({ tier, className }: { tier: SettingsTier; className?: string }) {
  const scope = SETTINGS_TIER_SCOPE[tier]
  const Icon = TIER_ICON[tier]
  return (
    <p data-settings-scope={tier} className={cn("flex items-start gap-2 text-xs leading-relaxed text-muted-foreground", className)}>
      <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[color:var(--g-brand)]" aria-hidden="true" />
      <span className="min-w-0 text-pretty">
        <span className="font-medium text-foreground">{scope.label}</span>
        <span aria-hidden="true">{" · "}</span>
        <span className="sr-only">. </span>
        {scope.detail}
      </span>
    </p>
  )
}

function TierHeading({ tier }: { tier: SettingsTier }) {
  return (
    <div className="flex items-center justify-between gap-2 px-3 pb-2 pt-[18px] text-xs">
      <p className="font-semibold text-[color:var(--g-text-primary)]">{SETTINGS_TIER_LABELS[tier]}</p>
      <p className="inline-flex items-center gap-1 text-muted-foreground">
        {tier === "admin" ? <Lock className="h-3 w-3" aria-hidden /> : null}
        {SETTINGS_TIER_SCOPE[tier].label}
      </p>
    </div>
  )
}

/** Sections in a tier whose title or description matches the search text. */
function matchingSections(tier: SettingsTier, isAdmin: boolean, query: string) {
  const needle = query.trim().toLowerCase()
  const sections = settingsSectionsForTier(tier, isAdmin)
  if (!needle) return sections
  return sections.filter((section) =>
    `${section.title} ${section.description} ${SETTINGS_TIER_LABELS[tier]}`.toLowerCase().includes(needle),
  )
}

function SettingsNavSearch({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const id = useId()
  return (
    <div className="flex min-h-11 items-center gap-2.5 rounded-[10px] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-2)] px-3 text-muted-foreground focus-within:border-[color:var(--g-brand)] focus-within:bg-[color:var(--g-surface-1)] focus-within:ring-4 focus-within:ring-[color:var(--g-brand-soft)]">
      <Search className="h-4 w-4 shrink-0" aria-hidden />
      <label htmlFor={id} className="sr-only">Search settings</label>
      <input
        id={id}
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Escape" && value) {
            event.preventDefault()
            onChange("")
          }
        }}
        placeholder="Search settings"
        className="min-w-0 flex-1 border-0 bg-transparent text-sm text-[color:var(--g-text-primary)] outline-none placeholder:text-muted-foreground"
      />
    </div>
  )
}

function SettingsNavGroups({
  tiers,
  isAdmin,
  query,
  activeSection,
  onSectionChange,
  onNavigate,
}: {
  tiers: SettingsTier[]
  isAdmin: boolean
  query: string
  activeSection: SettingsSectionId
  onSectionChange?: (section: SettingsSectionId) => void
  onNavigate?: () => void
}) {
  const groups = tiers
    .map((tier) => ({ tier, sections: matchingSections(tier, isAdmin, query) }))
    .filter((group) => group.sections.length > 0)
  if (groups.length === 0) {
    return (
      <p role="status" className="px-3 pt-4 text-sm text-muted-foreground">
        No settings match &ldquo;{query.trim()}&rdquo;.
      </p>
    )
  }
  return (
    <>
      {groups.map(({ tier, sections }) => (
        <div key={tier}>
          <TierHeading tier={tier} />
          <div className="space-y-0.5">
            {sections.map((section) => (
              <SettingsNavItem
                key={section.id}
                section={section}
                activeSection={activeSection}
                onSectionChange={onSectionChange}
                onNavigate={onNavigate}
              />
            ))}
          </div>
        </div>
      ))}
    </>
  )
}

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
  const [query, setQuery] = useState("")
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
            {activeMeta ? <ScopeLine tier={activeMeta.tier} className="mt-2" /> : null}
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
        <nav aria-label="Settings section sheet" className="px-4 pb-6">
          <SettingsNavSearch value={query} onChange={setQuery} />
          <SettingsNavGroups
            tiers={tiers}
            isAdmin={isAdmin}
            query={query}
            activeSection={activeSection}
            onSectionChange={onSectionChange}
            onNavigate={() => setMenuOpen(false)}
          />
        </nav>
      </SheetContent>

      <aside className="relative z-30 hidden min-h-full w-[280px] shrink-0 self-stretch border-r border-divide bg-[color:var(--g-surface-1)] px-4 pb-10 pt-6 lg:block">
        <p className="px-3 pb-3.5 text-xl font-semibold tracking-[-0.01em] text-[color:var(--g-text-primary)]">Settings</p>
        <SettingsNavSearch value={query} onChange={setQuery} />
        <nav aria-label="Settings sections">
          <SettingsNavGroups
            tiers={tiers}
            isAdmin={isAdmin}
            query={query}
            activeSection={activeSection}
            onSectionChange={onSectionChange}
          />
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
              {activeMeta ? <ScopeLine tier={activeMeta.tier} className="mt-3" /> : null}
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
    "group flex min-h-11 w-full items-center gap-3 rounded-[9px] px-3 py-2 text-left text-sm font-medium transition-colors motion-reduce:transition-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--g-brand)] lg:min-h-10",
    isActive
      ? "bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand-active)] dark:text-[color:var(--g-brand)]"
      : "text-[color:var(--g-text-secondary)] hover:bg-[color:var(--g-surface-2)] hover:text-[color:var(--g-text-primary)]",
  )
  const iconClass = cn(
    "h-[18px] w-[18px] shrink-0",
    isActive ? "text-[color:var(--g-brand-active)] dark:text-[color:var(--g-brand)]" : "text-muted-foreground",
  )

  if (section.href) {
    return (
      <Link href={section.href} onClick={onNavigate} className={className} aria-current={isActive ? "page" : undefined}>
        <section.icon className={iconClass} aria-hidden />
        <span className="min-w-0 [overflow-wrap:anywhere]">{section.title}</span>
      </Link>
    )
  }

  return (
    <button type="button" aria-current={isActive ? "page" : undefined} onClick={() => { onNavigate?.(); onSectionChange?.(section.id) }} className={className}>
      <section.icon className={iconClass} aria-hidden />
      <span className="min-w-0 [overflow-wrap:anywhere]">{section.title}</span>
    </button>
  )
}

export function canAccessSettingsSection(section: SettingsSectionId, isAdmin: boolean): boolean {
  if (!ADMIN_ONLY_SETTINGS_SECTIONS.has(section)) return true
  return isAdmin
}
