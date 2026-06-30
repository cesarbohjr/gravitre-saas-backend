"use client"

import { useMemo, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { Search, CornerDownLeft } from "lucide-react"

import type { DocSearchItem } from "@/lib/docs/load-docs"

function scoreMatch(item: DocSearchItem, query: string): number {
  const q = query.toLowerCase()
  const title = item.title.toLowerCase()
  if (title === q) return 100
  if (title.startsWith(q)) return 80
  if (title.includes(q)) return 60
  if (item.category.toLowerCase().includes(q)) return 40
  if (item.description.toLowerCase().includes(q)) return 20
  return 0
}

export function DocsSearch({
  index,
  placeholder = "Search the docs…",
  autoFocus = false,
}: {
  index: DocSearchItem[]
  placeholder?: string
  autoFocus?: boolean
}) {
  const router = useRouter()
  const [query, setQuery] = useState("")
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const blurTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const results = useMemo(() => {
    if (query.trim().length < 2) return []
    return index
      .map((item) => ({ item, score: scoreMatch(item, query.trim()) }))
      .filter((r) => r.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 8)
      .map((r) => r.item)
  }, [index, query])

  function go(slug: string) {
    setOpen(false)
    setQuery("")
    router.push(`/docs/${slug}`)
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.nativeEvent.isComposing || e.keyCode === 229) return
    if (!results.length) return
    if (e.key === "ArrowDown") {
      e.preventDefault()
      setActive((i) => (i + 1) % results.length)
    } else if (e.key === "ArrowUp") {
      e.preventDefault()
      setActive((i) => (i - 1 + results.length) % results.length)
    } else if (e.key === "Enter") {
      e.preventDefault()
      const target = results[active] ?? results[0]
      if (target) go(target.slug)
    } else if (e.key === "Escape") {
      setOpen(false)
    }
  }

  const showDropdown = open && query.trim().length >= 2

  return (
    <div className="relative w-full">
      <div className="flex items-center gap-3 rounded-xl border border-zinc-200 bg-white px-4 py-3 shadow-sm transition-colors focus-within:border-emerald-400 focus-within:ring-2 focus-within:ring-emerald-100">
        <Search className="h-5 w-5 shrink-0 text-zinc-400" aria-hidden="true" />
        <input
          type="text"
          value={query}
          autoFocus={autoFocus}
          onChange={(e) => {
            setQuery(e.target.value)
            setActive(0)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => {
            blurTimer.current = setTimeout(() => setOpen(false), 120)
          }}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          className="w-full bg-transparent text-sm text-zinc-900 placeholder:text-zinc-400 focus:outline-none"
          role="combobox"
          aria-expanded={showDropdown}
          aria-controls="docs-search-results"
          aria-label="Search documentation"
        />
      </div>

      {showDropdown && (
        <div
          id="docs-search-results"
          role="listbox"
          className="absolute left-0 right-0 top-full z-50 mt-2 overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-xl"
          onMouseDown={() => {
            if (blurTimer.current) clearTimeout(blurTimer.current)
          }}
        >
          {results.length === 0 ? (
            <p className="px-4 py-6 text-center text-sm text-zinc-500">
              No results for &ldquo;{query.trim()}&rdquo;
            </p>
          ) : (
            <ul className="max-h-80 overflow-y-auto py-1">
              {results.map((item, i) => (
                <li key={item.slug}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={i === active}
                    onMouseEnter={() => setActive(i)}
                    onClick={() => go(item.slug)}
                    className={`flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left transition-colors ${
                      i === active ? "bg-emerald-50" : "hover:bg-zinc-50"
                    }`}
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium text-zinc-900">
                        {item.title}
                      </span>
                      <span className="block truncate text-xs text-zinc-500">{item.category}</span>
                    </span>
                    {i === active && (
                      <CornerDownLeft className="h-3.5 w-3.5 shrink-0 text-emerald-500" aria-hidden="true" />
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
