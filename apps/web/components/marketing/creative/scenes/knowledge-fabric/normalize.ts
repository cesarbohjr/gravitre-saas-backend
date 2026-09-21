/**
 * Illustrative mention normalization — Decision A (CES 2.0 Cesar review).
 *
 * A small deterministic function is shared by fixtures and display so the
 * NORMALIZE step is inspectable and never contradicts implementation.
 *
 * Rules (documented, illustrative only — not live CRM ER):
 * 1. Unicode trim
 * 2. Collapse internal whitespace to single spaces
 * 3. Lowercase
 * 4. Strip trailing punctuation (. , ; : ! ?)
 *
 * This is NOT fuzzy person matching. "Sarah" and "Sarah Smith" normalize to
 * different strings and never share an entity key.
 */

export function normalizeIllustrativeMention(raw: string): string {
  return raw
    .trim()
    .replace(/\s+/g, " ")
    .toLowerCase()
    .replace(/[.,;:!?]+$/g, "")
}

export type IllustrativeMentionFixture = {
  id: string
  raw: string
  source: "crm" | "email"
  /** When set, exact normalized match group; null = never converge with others */
  entityKey: string | null
  fuzzyPersonDemo?: boolean
}

/** Fixtures — normalized values derived via normalizeIllustrativeMention at use sites. */
export const KF_A_MENTIONS: IllustrativeMentionFixture[] = [
  { id: "m1", raw: "Acme Corp", source: "crm", entityKey: "acme-corp" },
  { id: "m2", raw: "acme corp.", source: "email", entityKey: "acme-corp" },
  { id: "m3", raw: "Sarah", source: "crm", entityKey: null, fuzzyPersonDemo: true },
  { id: "m4", raw: "Sarah Smith", source: "email", entityKey: null, fuzzyPersonDemo: true },
]

export function mentionWithNormalized(m: IllustrativeMentionFixture) {
  return { ...m, normalized: normalizeIllustrativeMention(m.raw) }
}

export function exactMatchIds(
  mentions: ReturnType<typeof mentionWithNormalized>[],
  selectedId: string | null,
): string[] {
  if (!selectedId) return []
  const selected = mentions.find((m) => m.id === selectedId)
  if (!selected?.entityKey) return []
  return mentions.filter((m) => m.entityKey === selected.entityKey && m.normalized === selected.normalized).map((m) => m.id)
}
