/** "Mar 12" for a real timestamp, "—" when none was reported. */
export function formatShortDate(value?: string | null): string {
  if (!value) return "—"
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return "—"
  const sameYear = parsed.getFullYear() === new Date().getFullYear()
  return parsed.toLocaleDateString(undefined, sameYear ? { month: "short", day: "numeric" } : { month: "short", day: "numeric", year: "numeric" })
}

/** Days since a timestamp, or null when none was reported. */
export function ageInDays(value?: string | null): number | null {
  if (!value) return null
  const parsed = new Date(value).getTime()
  if (Number.isNaN(parsed)) return null
  return Math.floor((Date.now() - parsed) / 86_400_000)
}
