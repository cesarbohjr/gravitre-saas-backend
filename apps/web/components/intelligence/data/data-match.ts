/**
 * Pure helpers for Intelligence › Data: how a dataset's metadata is matched
 * against what the person wants Gravitre to learn, and how provider field
 * names line up with the org's knowledge entity types. Everything here is
 * computed from real metadata the APIs return; nothing is estimated.
 */
import type { ExternalDatasetSummary } from "@/lib/api"
import type { TrainingDataset } from "@/types/api"

const STOPWORDS = new Set([
  "the", "and", "for", "with", "from", "into", "that", "this", "what", "which",
  "should", "learn", "gravitre", "our", "your", "you", "are", "how", "when",
  "who", "why", "will", "can", "about", "right", "data", "dataset", "datasets",
])

/** Search words worth matching: lowercase, 3+ chars, no filler words. */
export function searchTerms(query: string): string[] {
  const words = query
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((word) => word.length >= 3 && !STOPWORDS.has(word))
  return Array.from(new Set(words))
}

function stem(word: string): string {
  return word.replace(/(ies|es|s|ing|ed)$/, "")
}

export type FitLevel = "strong" | "good" | "partial" | "weak"

export type Fit = {
  matched: number
  total: number
  level: FitLevel
  /** 1–4 bars for the meter. */
  bars: number
  label: string
}

/**
 * Fit = how many of the search words appear in the dataset's name,
 * description and tags. Shown with its basis so the meter is never a guess.
 */
export function computeFit(terms: string[], haystackParts: Array<string | null | undefined>): Fit {
  const haystack = haystackParts.filter(Boolean).join(" ").toLowerCase()
  const tokens = new Set(haystack.split(/[^a-z0-9]+/).filter(Boolean).map(stem))
  const total = terms.length
  const matched = terms.filter((term) => tokens.has(stem(term)) || haystack.includes(term)).length
  const ratio = total === 0 ? 0 : matched / total
  if (total > 0 && ratio >= 0.75) return { matched, total, level: "strong", bars: 4, label: "Strong fit" }
  if (ratio >= 0.5) return { matched, total, level: "good", bars: 3, label: "Good fit" }
  if (ratio > 0) return { matched, total, level: "partial", bars: 2, label: "Partial fit" }
  return { matched, total, level: "weak", bars: 1, label: "Weak fit" }
}

export function fitBasis(fit: Fit): string {
  if (fit.total === 0) return "No search words to compare"
  return `Matches ${fit.matched} of ${fit.total} search word${fit.total === 1 ? "" : "s"} in its name, description or tags`
}

function humanize(value: string): string {
  const clean = value.replace(/[_-]+/g, " ").trim()
  return clean ? clean.charAt(0).toUpperCase() + clean.slice(1) : clean
}

/** Readable tags from provider tag strings like "modality:text" or "task_categories:text-classification". */
export function readableTags(tags: string[], limit = 2): string[] {
  const out: string[] = []
  const prefer = ["modality:", "format:", "task_categories:"]
  for (const prefix of prefer) {
    for (const tag of tags) {
      if (out.length >= limit) return out
      if (tag.startsWith(prefix)) {
        const label = humanize(tag.slice(prefix.length))
        if (label && !out.includes(label)) out.push(label)
      }
    }
  }
  for (const tag of tags) {
    if (out.length >= limit) break
    if (tag.includes(":")) continue
    const label = humanize(tag)
    if (label && label.length <= 24 && !out.includes(label)) out.push(label)
  }
  return out
}

export function externalHaystack(dataset: ExternalDatasetSummary): string[] {
  return [dataset.dataset_id, dataset.name, dataset.description ?? "", ...dataset.tags]
}

export function ownHaystack(dataset: TrainingDataset): string[] {
  return [dataset.name, dataset.description ?? "", dataset.type]
}

/** Field names a provider reports in its dataset card (Hugging Face `dataset_info.features`). */
export function reportedFields(cardData: Record<string, unknown> | undefined): string[] {
  if (!cardData) return []
  const info = cardData.dataset_info
  const infos = Array.isArray(info) ? info : info && typeof info === "object" ? [info] : []
  const names: string[] = []
  for (const entry of infos) {
    const features = (entry as Record<string, unknown>)?.features
    if (!Array.isArray(features)) continue
    for (const feature of features) {
      const name = feature && typeof feature === "object" ? (feature as Record<string, unknown>).name : null
      if (typeof name === "string" && name.trim() && !names.includes(name.trim())) names.push(name.trim())
    }
  }
  return names.slice(0, 12)
}

/** License from Hugging Face card data or Kaggle's inspect payload. */
export function reportedLicense(dataset: Record<string, unknown> | null | undefined): string | null {
  if (!dataset) return null
  const direct = dataset.license
  if (typeof direct === "string" && direct.trim()) return direct.trim()
  const card = dataset.cardData as Record<string, unknown> | undefined
  const fromCard = card?.license
  if (typeof fromCard === "string" && fromCard.trim()) return fromCard.trim()
  if (Array.isArray(fromCard) && typeof fromCard[0] === "string") return fromCard.join(", ")
  return null
}

/**
 * Match a provider field to one of the org's knowledge entity types by name.
 * Returns null when nothing lines up, which the page shows as "Not mapped".
 */
export function mapFieldToEntity(field: string, entityTypes: string[]): string | null {
  const f = stem(field.toLowerCase().replace(/[^a-z0-9]/g, ""))
  if (f.length < 3) return null
  for (const type of entityTypes) {
    const t = stem(type.toLowerCase().replace(/[^a-z0-9]/g, ""))
    if (t.length < 3) continue
    if (f === t || f.includes(t) || t.includes(f)) return type
  }
  return null
}

export function entityLabel(type: string): string {
  return humanize(type)
}
