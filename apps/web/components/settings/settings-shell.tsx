"use client"

import React, { useEffect, useId, useState } from "react"
import Link from "next/link"
import { Search } from "lucide-react"
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
import "./settings-kit.css"

/** Sections in a group whose title, id or group name matches the search text. */
function matchingSections(group: SettingsGroup, isAdmin: boolean, query: string) {
  const needle = query.trim().toLowerCase()
  const sections = settingsSectionsForGroup(group, isAdmin)
  if (!needle) return sections
  return sections.filter((section) =>
    `${section.title} ${section.id} ${settingsGroupLabel(group)}`.toLowerCase().includes(needle),
  )
}

function SettingsFind({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const id = useId()
  return (
    <div className="gs-find">
      <Search size={16} aria-hidden />
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
      <p role="status" className="gs-nav-empty">
        No settings match &ldquo;{query.trim()}&rdquo;.
      </p>
    )
  }
  return (
    <>
      {groups.map(({ group, sections }) => (
        <div key={group.id} className="gs-group">
          <span className="gs-group-label">{group.label}</span>
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
  /** Buttons on the right of the page header. */
  actions?: React.ReactNode
  /** Override the section's title, description or "Settings / Group" crumb. */
  title?: React.ReactNode
  description?: React.ReactNode
  crumb?: React.ReactNode
  children: React.ReactNode
}

/** "Settings / Workspace"; Governance pages read "Governance". */
function crumbFor(group: SettingsGroup | undefined): string {
  if (!group) return "Settings"
  if (group === "governance") return "Governance"
  return `Settings / ${settingsGroupLabel(group)}`
}

export function SettingsShell({
  activeSection,
  onSectionChange,
  isAdmin,
  mobileMenuOpen,
  onMobileMenuOpenChange,
  hideHeader,
  actions,
  title,
  description,
  crumb,
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
  const crumbText = crumb ?? crumbFor(activeMeta?.group)
  const heading = title ?? activeMeta?.title
  const lede = description ?? activeMeta?.description

  return (
    <Sheet open={isCompact && menuOpen} onOpenChange={setMenuOpen}>
      <div className="st5 gv-set relative h-full min-h-0 overflow-auto">
        <div className="gs-wrap">
          <aside className="gs-nav hidden lg:block" aria-label="Settings">
            <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
              <div className="gs-nav-head">
                <b>Settings</b>
                <span>Organization and workspace</span>
              </div>
              <SettingsFind value={query} onChange={setQuery} />
              <nav aria-label="Settings sections" className="gs-nav-groups">
                <SettingsNavGroups
                  isAdmin={isAdmin}
                  query={query}
                  activeSection={activeSection}
                  onSectionChange={onSectionChange}
                />
              </nav>
            </div>
          </aside>

          <main className="gs-main">
            <div className="gs-mobile">
              <span className="gs-crumb">{crumbText}</span>
              <SheetTrigger asChild>
                <Button variant="outline" className="min-h-11 shrink-0 gap-2" aria-label="Choose settings section">
                  Sections
                </Button>
              </SheetTrigger>
            </div>
            {!hideHeader ? (
              <div className="gs-head">
                <div>
                  <span className="gs-crumb">{crumbText}</span>
                  <h1>{heading}</h1>
                  {lede ? <p>{lede}</p> : null}
                </div>
                {actions ? <div className="gs-head-actions">{actions}</div> : null}
              </div>
            ) : null}
            {children}
          </main>
        </div>
      </div>
      <SheetContent
        side="left"
        className="st5 gv-set w-[min(92vw,360px)] overflow-y-auto p-0 sm:max-w-[360px] data-[state=open]:duration-200 [&>button]:size-11"
      >
        <SheetHeader className="pr-14">
          <SheetTitle className="font-sans">Settings sections</SheetTitle>
          <SheetDescription>Choose the settings you want to manage.</SheetDescription>
        </SheetHeader>
        <nav aria-label="Settings section sheet" className="px-4 pb-6" style={{ display: "flex", flexDirection: "column", gap: 18 }}>
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
  const Icon = section.icon
  const body = (
    <>
      <Icon size={17} strokeWidth={1.8} aria-hidden />
      <span className="min-w-0 [overflow-wrap:anywhere]">{section.title}</span>
    </>
  )
  if (section.href) {
    return (
      <Link
        href={section.href}
        onClick={onNavigate}
        className="gs-nav-item"
        aria-current={isActive ? "page" : undefined}
      >
        {body}
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
      className="gs-nav-item"
    >
      {body}
    </button>
  )
}

export function canAccessSettingsSection(section: SettingsSectionId, isAdmin: boolean): boolean {
  if (!ADMIN_ONLY_SETTINGS_SECTIONS.has(section)) return true
  return isAdmin
}
