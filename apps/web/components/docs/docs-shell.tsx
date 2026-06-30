"use client"

import { useEffect, useState } from "react"
import { usePathname } from "next/navigation"
import { Menu, X } from "lucide-react"
import type { TocHeading } from "@/lib/docs/toc"
import { DocsSidebar, type DocsNavSection } from "./docs-sidebar"
import { DocsToc, DocsTocMobile } from "./docs-toc"

export function DocsShell({
  sections,
  headings,
  children,
}: {
  sections: DocsNavSection[]
  headings: TocHeading[]
  children: React.ReactNode
}) {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const pathname = usePathname()

  // Close the mobile nav drawer whenever the route changes.
  useEffect(() => {
    setDrawerOpen(false)
  }, [pathname])

  // Lock body scroll while the drawer is open.
  useEffect(() => {
    if (drawerOpen) {
      document.body.style.overflow = "hidden"
      return () => {
        document.body.style.overflow = ""
      }
    }
  }, [drawerOpen])

  return (
    <div className="mx-auto flex w-full max-w-7xl gap-8 px-4 sm:px-6">
      {/* Desktop sidebar */}
      <aside className="hidden w-64 shrink-0 lg:block">
        <div className="sticky top-16 max-h-[calc(100vh-4rem)] overflow-y-auto">
          <DocsSidebar sections={sections} />
        </div>
      </aside>

      {/* Mobile nav trigger + drawer */}
      <div className="lg:hidden">
        <button
          type="button"
          onClick={() => setDrawerOpen(true)}
          className="fixed bottom-5 left-1/2 z-40 flex -translate-x-1/2 items-center gap-2 rounded-full border border-zinc-200 bg-white px-4 py-2.5 text-sm font-medium text-zinc-700 shadow-lg"
        >
          <Menu className="h-4 w-4" />
          Menu
        </button>
        {drawerOpen ? (
          <div className="fixed inset-0 z-50 flex">
            <button
              type="button"
              aria-label="Close menu"
              onClick={() => setDrawerOpen(false)}
              className="absolute inset-0 bg-zinc-900/40"
            />
            <div className="relative z-10 h-full w-80 max-w-[85vw] overflow-y-auto bg-white shadow-xl">
              <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3">
                <span className="text-sm font-semibold text-zinc-900">Documentation</span>
                <button
                  type="button"
                  onClick={() => setDrawerOpen(false)}
                  className="rounded-md p-1.5 text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900"
                  aria-label="Close"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              <div className="px-4">
                <DocsSidebar sections={sections} />
              </div>
            </div>
          </div>
        ) : null}
      </div>

      {/* Article column */}
      <main className="min-w-0 flex-1 py-8">
        <div className="mx-auto max-w-3xl">
          <DocsTocMobile headings={headings} />
          {children}
        </div>
      </main>

      {/* Right TOC rail */}
      <aside className="hidden w-56 shrink-0 xl:block">
        <div className="sticky top-16 max-h-[calc(100vh-4rem)] overflow-y-auto py-8">
          <DocsToc headings={headings} />
        </div>
      </aside>
    </div>
  )
}
