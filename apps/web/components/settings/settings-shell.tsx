"use client"

import React from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import {
  ADMIN_ONLY_SETTINGS_SECTIONS,
  FOOTER_SETTINGS_SECTIONS,
  PRIMARY_SETTINGS_SECTIONS,
  SETTINGS_SECTIONS,
  WIDE_SETTINGS_SECTIONS,
  type SettingsSectionId,
} from "@/lib/settings-sections"

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
  mobileMenuOpen = false,
  onMobileMenuOpenChange,
  hideHeader,
  children,
}: SettingsShellProps) {
  const activeMeta = SETTINGS_SECTIONS.find((section) => section.id === activeSection)
  const showHeader = !hideHeader
  const wide = WIDE_SETTINGS_SECTIONS.has(activeSection)

  const primary = PRIMARY_SETTINGS_SECTIONS
  const footer = FOOTER_SETTINGS_SECTIONS.filter((section) => !section.adminOnly || isAdmin)

  return (
    <div className="relative flex h-full min-h-0 flex-col md:flex-row">
      <div className="sticky top-0 z-20 flex items-center justify-between border-b border-border bg-card/80 px-4 py-3 backdrop-blur md:hidden">
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-lg font-semibold text-foreground">{activeMeta?.title}</h1>
          <p className="truncate text-xs text-muted-foreground">{activeMeta?.description}</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onMobileMenuOpenChange?.(!mobileMenuOpen)}
          className="ml-3 shrink-0 gap-2"
        >
          {activeMeta ? <activeMeta.icon className="h-4 w-4" /> : null}
          <span className="sr-only">Menu</span>
        </Button>
      </div>

      {mobileMenuOpen ? (
        <div className="z-20 border-b border-border bg-card md:hidden">
          <div className="grid grid-cols-2 gap-2 p-3">
            {[...primary, ...footer].map((section) => (
              <SettingsNavItem
                key={section.id}
                section={section}
                activeSection={activeSection}
                onSectionChange={(id) => {
                  onSectionChange?.(id)
                  onMobileMenuOpenChange?.(false)
                }}
                compact
              />
            ))}
          </div>
        </div>
      ) : null}

      <aside className="relative z-30 hidden w-64 shrink-0 border-r border-border bg-card/95 p-4 backdrop-blur-sm md:block">
        <nav className="space-y-1" aria-label="Settings sections">
          {primary.map((section) => (
            <SettingsNavItem
              key={section.id}
              section={section}
              activeSection={activeSection}
              onSectionChange={onSectionChange}
            />
          ))}
          <div className="my-3 border-t border-border/70" />
          {footer.map((section) => (
            <SettingsNavItem
              key={section.id}
              section={section}
              activeSection={activeSection}
              onSectionChange={onSectionChange}
            />
          ))}
        </nav>
      </aside>

      <div className="relative z-10 min-w-0 flex-1 overflow-auto">
        <div
          className={cn(
            "mx-auto",
            hideHeader
              ? cn(wide ? "max-w-5xl" : "max-w-2xl md:mx-0")
              : cn("p-4 md:p-6", wide ? "max-w-5xl" : "max-w-2xl md:mx-0"),
          )}
        >
          {showHeader ? (
            <div className="mb-6 hidden md:block">
              <h1 className="mb-1 text-xl font-semibold text-foreground">{activeMeta?.title}</h1>
              <p className="text-sm text-muted-foreground">{activeMeta?.description}</p>
            </div>
          ) : null}
          {children}
        </div>
      </div>
    </div>
  )
}

function SettingsNavItem({
  section,
  activeSection,
  onSectionChange,
  compact,
}: {
  section: (typeof SETTINGS_SECTIONS)[number]
  activeSection: SettingsSectionId
  onSectionChange?: (section: SettingsSectionId) => void
  compact?: boolean
}) {
  const isActive = activeSection === section.id
  const className = cn(
    "flex w-full items-center gap-3 rounded-lg px-3 text-left text-sm transition-colors",
    compact ? "py-3" : "py-2",
    isActive
      ? "bg-primary/10 font-medium text-primary"
      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
  )

  if (section.href) {
    return (
      <Link href={section.href} className={className} aria-current={isActive ? "page" : undefined}>
        <section.icon className="h-4 w-4 shrink-0" />
        <span className="truncate">{section.title}</span>
      </Link>
    )
  }

  return (
    <button type="button" onClick={() => onSectionChange?.(section.id)} className={className}>
      <section.icon className="h-4 w-4 shrink-0" />
      <span className="truncate">{section.title}</span>
    </button>
  )
}

export function canAccessSettingsSection(section: SettingsSectionId, isAdmin: boolean): boolean {
  if (!ADMIN_ONLY_SETTINGS_SECTIONS.has(section)) return true
  return isAdmin
}
