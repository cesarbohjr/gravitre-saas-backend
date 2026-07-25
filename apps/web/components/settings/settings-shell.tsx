"use client"

import React from "react"
import Link from "next/link"
import { FileText, Lock } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import {
  ADMIN_ONLY_SETTINGS_SECTIONS,
  SETTINGS_SECTIONS,
  type SettingsSectionId,
} from "@/lib/settings-sections"

interface SettingsShellProps {
  activeSection: SettingsSectionId
  onSectionChange?: (section: SettingsSectionId) => void
  isAdmin: boolean
  mobileMenuOpen?: boolean
  onMobileMenuOpenChange?: (open: boolean) => void
  children: React.ReactNode
}

export function SettingsShell({
  activeSection,
  onSectionChange,
  isAdmin,
  mobileMenuOpen = false,
  onMobileMenuOpenChange,
  children,
}: SettingsShellProps) {
  const activeMeta = SETTINGS_SECTIONS.find((section) => section.id === activeSection)

  return (
    <div className="flex h-full flex-col md:flex-row">
      <div className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-card/50 p-4 md:hidden">
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
          <span className="sr-only md:not-sr-only">Menu</span>
        </Button>
      </div>

      {mobileMenuOpen ? (
        <div className="border-b border-border bg-card md:hidden">
          <div className="grid grid-cols-2 gap-2 p-3">
            {SETTINGS_SECTIONS.map((section) => (
              <SettingsNavItem
                key={section.id}
                section={section}
                activeSection={activeSection}
                onSectionChange={(id) => {
                  onSectionChange?.(id)
                  onMobileMenuOpenChange?.(false)
                }}
              />
            ))}
          </div>
        </div>
      ) : null}

      <div className="hidden w-64 shrink-0 border-r border-border p-4 md:block">
        <nav className="space-y-1">
          {SETTINGS_SECTIONS.map((section) => (
            <SettingsNavItem
              key={section.id}
              section={section}
              activeSection={activeSection}
              onSectionChange={onSectionChange}
            />
          ))}
          <Link
            href="/settings/team/permissions"
            className="mt-4 flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
          >
            <Shield className="h-4 w-4 shrink-0" />
            <span>Role permissions</span>
          </Link>
          {isAdmin ? (
            <Link
              href="/settings/approvals"
              className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
            >
              <Lock className="h-4 w-4 shrink-0" />
              <span>Human-in-the-loop</span>
            </Link>
          ) : null}
          {isAdmin ? (
            <Link
              href="/audit"
              className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
            >
              <FileText className="h-4 w-4 shrink-0" />
              <span>Audit trail</span>
            </Link>
          ) : null}
        </nav>
      </div>

      <div className="flex-1 overflow-auto p-4 md:p-6">
        <div className={cn("mx-auto", activeSection === "billing" ? "max-w-5xl" : "max-w-2xl md:mx-0")}>
          {activeSection !== "billing" ? (
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
}: {
  section: (typeof SETTINGS_SECTIONS)[number]
  activeSection: SettingsSectionId
  onSectionChange?: (section: SettingsSectionId) => void
}) {
  const isActive = activeSection === section.id
  const className = cn(
    "flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition-colors",
    isActive
      ? "bg-accent text-accent-foreground"
      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
  )

  if (section.href) {
    return (
      <Link href={section.href} className={className}>
        <section.icon className="h-4 w-4 shrink-0" />
        <span>{section.title}</span>
      </Link>
    )
  }

  return (
    <button type="button" onClick={() => onSectionChange?.(section.id)} className={className}>
      <section.icon className="h-4 w-4 shrink-0" />
      <span>{section.title}</span>
    </button>
  )
}

export function canAccessSettingsSection(section: SettingsSectionId, isAdmin: boolean): boolean {
  if (!ADMIN_ONLY_SETTINGS_SECTIONS.has(section)) return true
  return isAdmin
}
