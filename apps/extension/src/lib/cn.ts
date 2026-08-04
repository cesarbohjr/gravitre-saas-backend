/**
 * Minimal class joiner. The extension deliberately avoids clsx/tailwind-merge
 * to keep the content-script bundle small — every byte here is parsed on
 * someone else's page.
 */
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ")
}
