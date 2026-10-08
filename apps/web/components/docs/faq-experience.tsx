"use client"

import { useMemo, useState, type ReactNode } from "react"
import { ChevronDown, Search, X } from "lucide-react"

export type FaqClientQuestion = {
  id: string
  question: string
  searchText: string
  answer: ReactNode
}

export type FaqClientSection = {
  id: string
  title: string
  intro: ReactNode | null
  questions: FaqClientQuestion[]
}

export function FaqExperience({ sections }: { sections: FaqClientSection[] }) {
  const [query, setQuery] = useState("")
  const [openIds, setOpenIds] = useState<Set<string>>(new Set())

  const normalizedQuery = query.trim().toLowerCase()
  const isSearching = normalizedQuery.length > 0

  const filteredSections = useMemo(() => {
    if (!isSearching) return sections
    return sections
      .map((section) => ({
        ...section,
        questions: section.questions.filter((q) => q.searchText.includes(normalizedQuery)),
      }))
      .filter((section) => section.questions.length > 0)
  }, [sections, normalizedQuery, isSearching])

  const totalMatches = filteredSections.reduce((sum, s) => sum + s.questions.length, 0)

  const toggle = (id: string) => {
    setOpenIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const isOpen = (id: string) => isSearching || openIds.has(id)

  return (
    <div className="grid grid-cols-1 gap-10 lg:grid-cols-[220px_minmax(0,1fr)]">
      {/* Section jump nav */}
      <aside className="hidden lg:block">
        <div className="sticky top-24">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Categories
          </p>
          <nav className="flex flex-col gap-1">
            {sections.map((section) => (
              <a
                key={section.id}
                href={`#${section.id}`}
                className="rounded-md px-2 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                {section.title}
              </a>
            ))}
          </nav>
        </div>
      </aside>

      <div>
        {/* Search */}
        <div className="relative mb-8">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search frequently asked questions…"
            aria-label="Search FAQ"
            className="w-full rounded-xl border border-border bg-card py-3 pl-11 pr-10 text-sm text-foreground shadow-sm outline-none transition-colors placeholder:text-muted-foreground focus:border-brand focus:ring-2 focus:ring-brand-soft"
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery("")}
              aria-label="Clear search"
              className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {isSearching && (
          <p className="mb-6 text-sm text-muted-foreground">
            {totalMatches === 0
              ? "No matching questions."
              : `${totalMatches} ${totalMatches === 1 ? "result" : "results"} for "${query}"`}
          </p>
        )}

        {totalMatches === 0 && isSearching ? (
          <div className="rounded-xl border border-dashed border-border-control px-6 py-12 text-center">
            <p className="text-sm text-muted-foreground">
              Nothing here matches your search. Try different keywords, or{" "}
              <a href="/contact" className="font-medium text-brand-text hover:text-brand-text/80">
                contact support
              </a>
              .
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-10">
            {filteredSections.map((section) => (
              <section key={section.id} id={section.id} className="scroll-mt-24">
                <h2 className="mb-4 text-lg font-semibold text-foreground">{section.title}</h2>
                {section.intro ? (
                  <div className="prose prose-sm mb-4 max-w-none">{section.intro}</div>
                ) : null}
                <div className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card">
                  {section.questions.map((q) => {
                    const open = isOpen(q.id)
                    return (
                      <div key={q.id} id={q.id} className="scroll-mt-24">
                        <button
                          type="button"
                          onClick={() => toggle(q.id)}
                          aria-expanded={open}
                          className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left transition-colors hover:bg-surface-hover"
                        >
                          <span className="text-sm font-medium text-foreground">{q.question}</span>
                          <ChevronDown
                            className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${
                              open ? "rotate-180" : ""
                            }`}
                          />
                        </button>
                        {open && (
                          <div className="prose prose-sm max-w-none px-5 pb-5 pt-0 text-muted-foreground">
                            {q.answer}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </section>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
