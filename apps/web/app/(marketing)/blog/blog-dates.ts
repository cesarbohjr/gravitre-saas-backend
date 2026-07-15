const DISPLAY_FORMAT = new Intl.DateTimeFormat("en-US", {
  month: "long",
  day: "numeric",
  year: "numeric",
  timeZone: "UTC",
})

/** ISO calendar date (YYYY-MM-DD) for the day a post goes live. Defaults to today (UTC). */
export function toBlogIsoDate(date: Date = new Date()): string {
  return date.toISOString().slice(0, 10)
}

/** Human-readable label shown in the blog UI, e.g. "July 15, 2026". */
export function formatBlogDisplayDate(isoDate: string): string {
  const [year, month, day] = isoDate.split("-").map(Number)
  return DISPLAY_FORMAT.format(new Date(Date.UTC(year, month - 1, day)))
}

/**
 * Blog post date fields. Set `datePublished` to the go-live day; bump `dateModified`
 * only when the article content changes after publish.
 */
export function createBlogDates(publishedIso: string, modifiedIso?: string) {
  const dateModified = modifiedIso ?? publishedIso
  return {
    datePublished: publishedIso,
    dateModified,
    displayDate: formatBlogDisplayDate(publishedIso),
  }
}
