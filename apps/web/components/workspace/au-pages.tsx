"use client"

/** Page numbers for a paged list: "‹ Prev 1 2 3 … Next ›", windowed around the current page. */
export function AuPages({
  page,
  pageCount,
  onPage,
  label = "Pages",
}: {
  /** 1-based current page. */
  page: number
  pageCount: number
  onPage: (page: number) => void
  label?: string
}) {
  if (pageCount <= 1) return null
  return (
    <nav className="au-pages" aria-label={label}>
      <button type="button" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        ‹ Prev
      </button>
      {pageWindow(page, pageCount).map((n, index) =>
        n === null ? (
          <span key={`gap-${index}`} aria-hidden>
            …
          </span>
        ) : (
          <button
            key={n}
            type="button"
            aria-current={n === page ? "page" : undefined}
            aria-label={`Page ${n}`}
            onClick={() => onPage(n)}
          >
            {n}
          </button>
        ),
      )}
      <button type="button" disabled={page >= pageCount} onClick={() => onPage(page + 1)}>
        Next ›
      </button>
    </nav>
  )
}

/** Every page when there are few; otherwise first, last and the pages around the current one, gaps as null. */
export function pageWindow(page: number, pageCount: number): Array<number | null> {
  if (pageCount <= 7) return Array.from({ length: pageCount }, (_, i) => i + 1)
  const keep = [1, pageCount, page - 1, page, page + 1].filter((n) => n >= 1 && n <= pageCount)
  const sorted = Array.from(new Set(keep)).sort((x, y) => x - y)
  const out: Array<number | null> = []
  for (const n of sorted) {
    const prev = out[out.length - 1]
    if (typeof prev === "number" && n - prev > 1) out.push(null)
    out.push(n)
  }
  return out
}

/** Slice of one page; clamps the page so a shrinking list never shows an empty page. */
export function paginate<T>(rows: T[], page: number, pageSize: number): { rows: T[]; page: number; pageCount: number; from: number; to: number } {
  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize))
  const current = Math.min(Math.max(1, page), pageCount)
  const start = (current - 1) * pageSize
  const slice = rows.slice(start, start + pageSize)
  return { rows: slice, page: current, pageCount, from: rows.length ? start + 1 : 0, to: start + slice.length }
}
