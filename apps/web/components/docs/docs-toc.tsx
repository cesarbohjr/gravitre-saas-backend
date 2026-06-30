"use client"

import { useEffect, useState } from "react"
import type { TocHeading } from "@/lib/docs/toc"

function useActiveHeading(ids: string[]): string | null {
  const [activeId, setActiveId] = useState<string | null>(ids[0] ?? null)

  useEffect(() => {
    if (ids.length === 0) return

    const elements = ids
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => el !== null)

    if (elements.length === 0) return

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
        if (visible[0]) {
          setActiveId(visible[0].target.id)
        }
      },
      // Bias toward the heading nearest the top of the viewport.
      { rootMargin: "-80px 0px -70% 0px", threshold: [0, 1] },
    )

    elements.forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [ids])

  return activeId
}

export function DocsToc({ headings }: { headings: TocHeading[] }) {
  const activeId = useActiveHeading(headings.map((h) => h.id))

  if (headings.length < 2) return null

  return (
    <nav aria-label="On this page" className="text-sm">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-zinc-500">
        On this page
      </p>
      <ul className="space-y-1.5 border-l border-zinc-200">
        {headings.map((heading) => {
          const active = heading.id === activeId
          return (
            <li key={heading.id}>
              <a
                href={`#${heading.id}`}
                className={`-ml-px block border-l-2 py-0.5 transition-colors ${
                  heading.depth === 3 ? "pl-6" : "pl-3"
                } ${
                  active
                    ? "border-emerald-500 font-medium text-emerald-700"
                    : "border-transparent text-zinc-500 hover:border-zinc-300 hover:text-zinc-900"
                }`}
              >
                {heading.text}
              </a>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

/** Mobile "On this page" disclosure shown above the article on small screens. */
export function DocsTocMobile({ headings }: { headings: TocHeading[] }) {
  const [open, setOpen] = useState(false)

  if (headings.length < 2) return null

  return (
    <details
      open={open}
      onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
      className="mb-8 rounded-xl border border-zinc-200 bg-zinc-50/60 p-3 xl:hidden"
    >
      <summary className="cursor-pointer list-none text-sm font-medium text-zinc-700">
        On this page
      </summary>
      <ul className="mt-3 space-y-1.5 border-l border-zinc-200">
        {headings.map((heading) => (
          <li key={heading.id}>
            <a
              href={`#${heading.id}`}
              onClick={() => setOpen(false)}
              className={`block py-0.5 text-sm text-zinc-600 hover:text-emerald-700 ${
                heading.depth === 3 ? "pl-6" : "pl-3"
              }`}
            >
              {heading.text}
            </a>
          </li>
        ))}
      </ul>
    </details>
  )
}
