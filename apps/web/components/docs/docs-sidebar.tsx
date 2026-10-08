"use client"

import { createElement, useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { ChevronRight } from "lucide-react"

import { categoryIcon } from "./category-meta"

export interface DocsNavItem {
  title: string
  href: string
}

export interface DocsNavSection {
  title: string
  items: DocsNavItem[]
}

/** Preferred display order for sidebar categories; unknown categories sort last. */
const CATEGORY_ORDER = [
  "Getting Started",
  "Core Concepts",
  "How-to Guides",
  "Integrations",
  "API Reference",
  "Security",
  "Billing",
  "FAQ",
]

export function orderSections(sections: DocsNavSection[]): DocsNavSection[] {
  return [...sections].sort((a, b) => {
    const ai = CATEGORY_ORDER.indexOf(a.title)
    const bi = CATEGORY_ORDER.indexOf(b.title)
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi)
  })
}

function CategoryIcon({ category, className }: { category: string; className?: string }) {
  return createElement(categoryIcon(category), { className })
}

function SidebarSection({
  section,
  activeHref,
}: {
  section: DocsNavSection
  activeHref: string
}) {
  const containsActive = section.items.some((item) => item.href === activeHref)
  const [open, setOpen] = useState(containsActive)

  return (
    <div className="mb-1">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground transition-colors hover:text-foreground"
      >
        <span className="flex items-center gap-2">
          <CategoryIcon category={section.title} className="h-3.5 w-3.5 text-muted-foreground" />
          {section.title}
        </span>
        <ChevronRight
          className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-90" : ""}`}
        />
      </button>
      {open ? (
        <ul className="mt-1 space-y-0.5 border-l border-border pl-3">
          {section.items.map((item) => {
            const active = item.href === activeHref
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={`block rounded-md px-2 py-1.5 text-sm transition-colors ${
                    active
                      ? "bg-brand-soft font-medium text-brand-text"
                      : "text-muted-foreground hover:bg-surface-hover hover:text-foreground"
                  }`}
                >
                  {item.title}
                </Link>
              </li>
            )
          })}
        </ul>
      ) : null}
    </div>
  )
}

export function DocsSidebar({ sections }: { sections: DocsNavSection[] }) {
  const pathname = usePathname()
  const ordered = orderSections(sections)

  return (
    <nav aria-label="Documentation" className="py-8 pr-4">
      <Link
        href="/docs"
        className={`mb-4 block rounded-md px-2 py-1.5 text-sm font-medium transition-colors ${
          pathname === "/docs"
            ? "bg-brand-soft text-brand-text"
            : "text-foreground hover:bg-surface-hover hover:text-foreground"
        }`}
      >
        Documentation home
      </Link>
      {ordered.map((section) => (
        <SidebarSection key={section.title} section={section} activeHref={pathname} />
      ))}
    </nav>
  )
}
