"use client"

import React, { useEffect, useId, useState } from "react"
import Link from "next/link"
import { Lock, Search } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { useIsMobile } from "@/hooks/use-mobile"
import {
  ADMIN_ONLY_SETTINGS_SECTIONS,
  SETTINGS_GROUPS,
  SETTINGS_SECTIONS,
  settingsGroupLabel,
  settingsSectionsForGroup,
  type SettingsGroup,
  type SettingsSectionId,
} from "@/lib/settings-sections"
import "./settings-v5.css"

/** Sections in a group whose title, description or id matches the search text. */
function matchingSections(group: SettingsGroup, isAdmin: boolean, query: string) {
  const needle = query.trim().toLowerCase()
  const sections = settingsSectionsForGroup(group, isAdmin)
  if (!needle) return sections
  return sections.filter((section) =>
    `${section.title} ${section.description} ${section.id} ${settingsGroupLabel(group)}`.toLowerCase().includes(needle),
  )
}

function SettingsFind({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const id = useId()
  return (
    <div className="st-find">
      <Search size={14} aria-hidden />
      <label htmlFor={id} className="sr-only">
        Find a setting
      </label>
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
        placeholder="Find a setting"
      />
    </div>
  )
}

function SettingsNavGroups({
  isAdmin,
  query,
  activeSection,
  onSectionChange,
  onNavigate,
}: {
  isAdmin: boolean
  query: string
  activeSection: SettingsSectionId
  onSectionChange?: (section: SettingsSectionId) => void
  onNavigate?: () => void
}) {
  const groups = SETTINGS_GROUPS.filter((group) => !group.locked || isAdmin)
    .map((group) => ({ group, sections: matchingSections(group.id, isAdmin, query) }))
    .filter((row) => row.sections.length > 0)
  if (groups.length === 0) {
    return (
      <p role="status" className="st-nav-empty">
        No settings match &ldquo;{query.trim()}&rdquo;.
      </p>
    )
  }
  return (
    <>
      {groups.map(({ group, sections }) => (
        <div key={group.id} className="st-group">
          <span className="st-group-label">
            {group.label}
            {group.locked ? (
              <span className="lock">
                <Lock size={11} strokeWidth={2.4} aria-hidden />
                Admins only
              </span>
            ) : null}
          </span>
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
  /** Hide the default title block (page supplies its own hero). */
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
  const groupLabel = activeMeta ? settingsGroupLabel(activeMeta.group) : "Workspace"

  return (
    <Sheet open={isCompact && menuOpen} onOpenChange={setMenuOpen}>
      <div className="st5 relative h-full min-h-0 overflow-auto">
        <div className="st-wrap">
          <aside className="st-nav hidden min-h-full self-stretch lg:block" aria-label="Settings navigation">
            <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
              <div className="st-nav-head">
                <b>Settings</b>
                <span>Organization and workspace</span>
              </div>
              <SettingsFind value={query} onChange={setQuery} />
              <nav aria-label="Settings sections" style={{ display: "flex", flexDirection: "column", gap: 22 }}>
                <SettingsNavGroups
                  isAdmin={isAdmin}
                  query={query}
                  activeSection={activeSection}
                  onSectionChange={onSectionChange}
                />
              </nav>
            </div>
          </aside>

          <main className="st-main">
            <div className="st-mobile">
              <span className="st-crumb">Settings / {groupLabel}</span>
              <SheetTrigger asChild>
                <Button variant="outline" className="min-h-11 shrink-0 gap-2" aria-label="Choose settings section">
                  Sections
                </Button>
              </SheetTrigger>
            </div>
            {!hideHeader ? (
              <div className="st-head">
                <span className="st-crumb">Settings / {groupLabel}</span>
                <h1>{activeMeta?.title}</h1>
                {activeMeta?.description ? <p>{activeMeta.description}</p> : null}
              </div>
            ) : null}
            {children}
          </main>
        </div>
      </div>
      <SheetContent
        side="left"
        className="st5 w-[min(92vw,360px)] overflow-y-auto p-0 sm:max-w-[360px] data-[state=open]:duration-200 [&>button]:size-11"
      >
        <SheetHeader className="pr-14">
          <SheetTitle className="font-sans">Settings sections</SheetTitle>
          <SheetDescription>Choose the settings you want to manage.</SheetDescription>
        </SheetHeader>
        <nav aria-label="Settings section sheet" className="px-4 pb-6" style={{ display: "flex", flexDirection: "column", gap: 22 }}>
          <SettingsFind value={query} onChange={setQuery} />
          <SettingsNavGroups
            isAdmin={isAdmin}
            query={query}
            activeSection={activeSection}
            onSectionChange={onSectionChange}
            onNavigate={() => setMenuOpen(false)}
          />
        </nav>
      </SheetContent>
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
  if (section.href) {
    return (
      <Link
        href={section.href}
        onClick={onNavigate}
        className="st-nav-item"
        aria-current={isActive ? "page" : undefined}
      >
        <span className="bar" aria-hidden />
        <span className="min-w-0 [overflow-wrap:anywhere]">{section.title}</span>
      </Link>
    )
  }
  return (
    <button
      type="button"
      aria-current={isActive ? "page" : undefined}
      onClick={() => {
        onNavigate?.()
        onSectionChange?.(section.id)
      }}
      className="st-nav-item"
    >
      <span className="bar" aria-hidden />
      <span className="min-w-0 [overflow-wrap:anywhere]">{section.title}</span>
    </button>
  )
}

export function canAccessSettingsSection(section: SettingsSectionId, isAdmin: boolean): boolean {
  if (!ADMIN_ONLY_SETTINGS_SECTIONS.has(section)) return true
  return isAdmin
}
