/**
 * Knowledge's in-page views (Graph / Entities / Memory). The active view lives
 * in the URL as `?view=`; the legacy `#memory` anchor (and /intelligence/memory,
 * which redirects to it) selects Memory.
 */
export type KnowledgeView = "graph" | "entities" | "memory"

export const KNOWLEDGE_VIEWS: readonly KnowledgeView[] = ["graph", "entities", "memory"] as const

export function isKnowledgeView(value: unknown): value is KnowledgeView {
  return value === "graph" || value === "entities" || value === "memory"
}

/** `?view=` wins; otherwise `#memory` selects Memory; otherwise Graph. */
export function resolveKnowledgeView(viewParam: string | null | undefined, hash: string | null | undefined): KnowledgeView {
  if (isKnowledgeView(viewParam)) return viewParam
  if ((hash ?? "").replace(/^#/, "") === "memory") return "memory"
  return "graph"
}

/** Search string for a view, keeping every other query param. Graph is the default, so it drops `view`. */
export function knowledgeViewSearch(current: string, view: KnowledgeView): string {
  const params = new URLSearchParams(current)
  if (view === "graph") params.delete("view")
  else params.set("view", view)
  const query = params.toString()
  return query ? `?${query}` : ""
}
