"use client"

import { useState } from "react"
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

function SidebarSection({
  section,
  activeHref,
}: {
  section: DocsNavSection
  activeHref: string
}) {
  const containsActive = section.items.some((item) => item.href === activeHref)
  const [open, setOpen] = useState(containsActive)
  const Icon = categoryIcon(section.title)

  return (
    <div className="mb-1">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-xs font-semibold uppercase tracking-wide text-zinc-500 transition-colors hover:text-zinc-900"
      >
        <span className="flex items-center gap-2">
          <Icon className="h-3.5 w-3.5 text-zinc-400" />
          {section.title}
        </span>
        <ChevronRight
          className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-90" : ""}`}
        />
      </button>
      {open ? (
        <ul className="mt-1 space-y-0.5 border-l border-zinc-200 pl-3">
          {section.items.map((item) => {
            const active = item.href === activeHref
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={`block rounded-md px-2 py-1.5 text-sm transition-colors ${
                    active
                      ? "bg-emerald-50 font-medium text-emerald-700"
                      : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900"
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
            ? "bg-emerald-50 text-emerald-700"
            : "text-zinc-700 hover:bg-zinc-50 hover:text-zinc-900"
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
