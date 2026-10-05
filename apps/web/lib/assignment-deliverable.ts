/**
 * Safe, non-executing interpretation of agent deliverable payloads.
 *
 * Agents return either prose/Markdown or a serialized object (sometimes with a
 * prefix like `Sales handoff JSON: {...}` or inside a ```json fence). Known
 * keys become semantic sections; every other key is kept as an additional
 * field so nothing the agent supplied is silently dropped. The original value
 * is always retained for "View original data".
 */

export type DeliverableSectionKind = "summary" | "recommendations" | "risks" | "next_steps" | "sources"

export type DeliverableSection = {
  kind: DeliverableSectionKind
  label: string
  /** Original key in the payload, for traceability. */
  sourceKey: string
  paragraphs: string[]
  items: string[]
}

export type DeliverableField = {
  key: string
  label: string
  /** Display value. `null` means the payload explicitly sent null. */
  value: string | null
  multiline: boolean
}

export type ParsedDeliverable =
  | {
      format: "structured"
      prefixLabel: string | null
      sections: DeliverableSection[]
      fields: DeliverableField[]
      original: string
      originalJson: string
    }
  | {
      format: "text"
      prefixLabel: null
      sections: []
      fields: []
      original: string
      originalJson: null
    }

const SECTION_KEYS: Array<{ kind: DeliverableSectionKind; label: string; keys: string[] }> = [
  {
    kind: "summary",
    label: "Summary",
    keys: ["summary", "executive_summary", "overview", "tldr", "answer", "result", "finding_description", "findings", "analysis"],
  },
  {
    kind: "recommendations",
    label: "Recommendations",
    keys: ["recommendations", "recommended_actions", "suggestions", "proposed_actions", "actions"],
  },
  { kind: "risks", label: "Risks", keys: ["risks", "risk", "concerns", "issues", "blockers", "warnings", "caveats"] },
  {
    kind: "next_steps",
    label: "Next steps",
    keys: ["next_steps", "nextsteps", "follow_ups", "followups", "action_items", "todo", "todos"],
  },
  { kind: "sources", label: "Sources", keys: ["sources", "references", "citations", "rag_sources", "evidence"] },
]

const READABLE_ITEM_KEYS = ["title", "name", "action", "description", "text", "summary", "detail", "source", "url", "content"]

function normalizeKey(key: string): string {
  return key
    .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
    .replace(/[\s-]+/g, "_")
    .toLowerCase()
}

export function humanizeKey(key: string): string {
  const words = normalizeKey(key).split("_").filter(Boolean)
  if (words.length === 0) return key
  const sentence = words.join(" ")
  return sentence.charAt(0).toUpperCase() + sentence.slice(1)
}

function itemToText(item: unknown): string {
  if (item === null) return "null"
  if (typeof item === "string") return item.trim()
  if (typeof item === "number" || typeof item === "boolean") return String(item)
  if (Array.isArray(item)) return item.map(itemToText).filter(Boolean).join(", ")
  if (typeof item === "object") {
    const record = item as Record<string, unknown>
    const parts: string[] = []
    for (const key of READABLE_ITEM_KEYS) {
      const value = record[key]
      if (typeof value === "string" && value.trim() && !parts.includes(value.trim())) parts.push(value.trim())
      if (parts.length === 2) break
    }
    if (parts.length > 0) return parts.join(" — ")
    return JSON.stringify(item)
  }
  return String(item)
}

function toSection(kind: DeliverableSectionKind, label: string, sourceKey: string, value: unknown): DeliverableSection | null {
  if (value === undefined) return null
  if (Array.isArray(value)) {
    const items = value.map(itemToText).filter((text) => text.length > 0)
    return items.length ? { kind, label, sourceKey, paragraphs: [], items } : null
  }
  if (typeof value === "string") {
    const text = value.trim()
    if (!text) return null
    return { kind, label, sourceKey, paragraphs: text.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean), items: [] }
  }
  if (value && typeof value === "object") {
    const items = Object.entries(value as Record<string, unknown>).map(
      ([key, entry]) => `${humanizeKey(key)}: ${itemToText(entry)}`,
    )
    return items.length ? { kind, label, sourceKey, paragraphs: [], items } : null
  }
  return { kind, label, sourceKey, paragraphs: [String(value)], items: [] }
}

function toField(key: string, value: unknown): DeliverableField {
  if (value === null) return { key, label: humanizeKey(key), value: null, multiline: false }
  if (typeof value === "string") return { key, label: humanizeKey(key), value, multiline: value.includes("\n") || value.length > 120 }
  if (typeof value === "number" || typeof value === "boolean") {
    return { key, label: humanizeKey(key), value: String(value), multiline: false }
  }
  const isFlatList = Array.isArray(value) && value.every((entry) => entry === null || typeof entry !== "object")
  if (isFlatList) {
    return { key, label: humanizeKey(key), value: (value as unknown[]).map(itemToText).join(", "), multiline: false }
  }
  return { key, label: humanizeKey(key), value: JSON.stringify(value, null, 2), multiline: true }
}

function stripFence(text: string): string {
  const fenced = text.match(/^```(?:json|JSON)?\s*\n([\s\S]*?)\n?```\s*$/)
  return fenced ? fenced[1] : text
}

/** Parse a JSON object/array embedded in text; returns null rather than throwing. */
function extractJson(text: string): { value: unknown; prefix: string } | null {
  const unfenced = stripFence(text.trim())
  const start = unfenced.search(/[[{]/)
  if (start < 0) return null
  const opener = unfenced[start]
  const end = unfenced.lastIndexOf(opener === "{" ? "}" : "]")
  if (end <= start) return null
  try {
    const value: unknown = JSON.parse(unfenced.slice(start, end + 1))
    if (!value || typeof value !== "object") return null
    // A JSON blob in the middle of prose is quoted content, not the payload.
    const trailing = unfenced.slice(end + 1).trim()
    if (trailing.length > 0) return null
    return { value, prefix: unfenced.slice(0, start).trim() }
  } catch {
    return null
  }
}

function prefixToLabel(prefix: string): string | null {
  const label = prefix.replace(/\bJSON\b/gi, "").replace(/[:\-–—]+\s*$/g, "").replace(/\s+/g, " ").trim()
  if (!label || label.length > 80) return null
  return label.charAt(0).toUpperCase() + label.slice(1)
}

function buildStructured(value: unknown, original: string, prefix: string): ParsedDeliverable {
  const sections: DeliverableSection[] = []
  const fields: DeliverableField[] = []

  if (Array.isArray(value)) {
    const section = toSection("summary", "Items", "(root)", value)
    if (section) sections.push(section)
  } else {
    const record = value as Record<string, unknown>
    const claimed = new Set<string>()
    for (const group of SECTION_KEYS) {
      for (const [key, entry] of Object.entries(record)) {
        if (claimed.has(key) || !group.keys.includes(normalizeKey(key))) continue
        // Only one summary-like key becomes the summary; others stay as fields.
        if (group.kind === "summary" && sections.some((s) => s.kind === "summary")) continue
        const section = toSection(group.kind, group.label, key, entry)
        if (section) {
          sections.push(section)
          claimed.add(key)
        }
      }
    }
    for (const [key, entry] of Object.entries(record)) {
      if (!claimed.has(key)) fields.push(toField(key, entry))
    }
  }

  return {
    format: "structured",
    prefixLabel: prefixToLabel(prefix),
    sections,
    fields,
    original,
    originalJson: JSON.stringify(value, null, 2),
  }
}

export function parseDeliverable(raw: unknown): ParsedDeliverable {
  if (raw && typeof raw === "object") {
    let original = ""
    try {
      original = JSON.stringify(raw)
    } catch {
      original = String(raw)
    }
    return buildStructured(raw, original, "")
  }
  const original = typeof raw === "string" ? raw : raw == null ? "" : String(raw)
  const extracted = extractJson(original)
  if (extracted) return buildStructured(extracted.value, original, extracted.prefix)
  return { format: "text", prefixLabel: null, sections: [], fields: [], original, originalJson: null }
}

/** One-line plain summary suitable for list rows and titles. */
export function deliverableHeadline(parsed: ParsedDeliverable, max = 160): string | null {
  const source =
    parsed.format === "structured"
      ? parsed.sections.find((s) => s.kind === "summary")?.paragraphs[0] ??
        parsed.sections.find((s) => s.kind === "summary")?.items[0] ??
        null
      : parsed.original
          .split("\n")
          .map((line) => line.replace(/^[#>*\-\s]+/, "").trim())
          .find(Boolean) ?? null
  if (!source) return null
  const flat = source.replace(/\s+/g, " ").trim()
  return flat.length > max ? `${flat.slice(0, max - 1)}…` : flat
}

export type TextBlock =
  | { type: "heading"; text: string }
  | { type: "paragraph"; text: string }
  | { type: "list"; ordered: boolean; items: string[] }

/** Minimal Markdown-ish block splitter. Output is rendered as React text, never HTML. */
export function toTextBlocks(text: string): TextBlock[] {
  const lines = text
    .replace(/\r\n/g, "\n")
    .split("\n")
    // Internal status tokens (e.g. `write_approval_required`) are not content.
    .filter((line) => !/^\s*[a-z][a-z0-9]*(?:_[a-z0-9]+)+\s*$/.test(line))
  const blocks: TextBlock[] = []
  let paragraph: string[] = []
  let list: { ordered: boolean; items: string[] } | null = null

  const flushParagraph = () => {
    if (paragraph.length) blocks.push({ type: "paragraph", text: paragraph.join(" ") })
    paragraph = []
  }
  const flushList = () => {
    if (list) blocks.push({ type: "list", ...list })
    list = null
  }

  for (const rawLine of lines) {
    const line = rawLine.trim()
    if (!line) {
      flushParagraph()
      flushList()
      continue
    }
    const heading = line.match(/^#{1,6}\s+(.*)$/)
    if (heading) {
      flushParagraph()
      flushList()
      blocks.push({ type: "heading", text: heading[1].replace(/\*\*/g, "") })
      continue
    }
    const bullet = line.match(/^[-*•]\s+(.*)$/)
    const numbered = line.match(/^\d+[.)]\s+(.*)$/)
    if (bullet || numbered) {
      flushParagraph()
      const ordered = Boolean(numbered)
      if (!list || list.ordered !== ordered) {
        flushList()
        list = { ordered, items: [] }
      }
      list.items.push((bullet ?? numbered)![1])
      continue
    }
    flushList()
    paragraph.push(line)
  }
  flushParagraph()
  flushList()
  return blocks
}
