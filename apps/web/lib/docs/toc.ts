import GithubSlugger from "github-slugger"

export interface TocHeading {
  /** Heading depth: 2 = h2, 3 = h3 */
  depth: 2 | 3
  /** Plain-text heading label (markdown stripped) */
  text: string
  /** Slug id — matches the id rehype-slug assigns to the rendered heading */
  id: string
}

/** Strip inline markdown (links, emphasis, code) down to display text. */
function stripInlineMarkdown(input: string): string {
  return input
    .replace(/`([^`]+)`/g, "$1") // inline code
    .replace(/\*\*([^*]+)\*\*/g, "$1") // bold
    .replace(/\*([^*]+)\*/g, "$1") // italic
    .replace(/_([^_]+)_/g, "$1") // underscore italic
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1") // links -> label
    .trim()
}

/**
 * Extract h2/h3 headings from raw MDX (frontmatter already stripped by the
 * loader) for the in-page table of contents. Uses github-slugger so the
 * generated ids match what rehype-slug assigns to the rendered headings.
 */
export function extractHeadings(source: string): TocHeading[] {
  const slugger = new GithubSlugger()
  const headings: TocHeading[] = []
  let inFence = false

  for (const rawLine of source.split("\n")) {
    const line = rawLine.trimEnd()

    // Track fenced code blocks (``` or ~~~) so "#" inside code is ignored.
    if (/^\s*(```|~~~)/.test(line)) {
      inFence = !inFence
      continue
    }
    if (inFence) continue

    const match = /^(#{2,3})\s+(.*)$/.exec(line)
    if (!match) continue

    const depth = match[1].length as 2 | 3
    const text = stripInlineMarkdown(match[2])
    if (!text) continue

    headings.push({ depth, text, id: slugger.slug(text) })
  }

  return headings
}
