"use client"

import { ConfidenceBadge } from "@/components/intelligence/confidence-badge"

export type KnowledgeCitation = {
  source_name?: string
  citation?: string
  jurisdiction?: string
  last_updated?: string | null
  effective_at?: string | null
  authority_score?: number | null
  freshness_score?: number | null
  authority_is_estimate?: boolean
  confidence_is_estimate?: boolean
  license_type?: string
  web_link?: string
}

/** Module C — knowledge-pack citation provenance (authority + freshness). */
export function KnowledgeCitationCard({
  citations,
  className,
}: {
  citations: KnowledgeCitation[]
  className?: string
}) {
  if (!citations?.length) return null
  return (
    <div className={className}>
      <p className="text-xs font-medium text-foreground">Knowledge pack citations</p>
      <ul className="mt-2 space-y-2">
        {citations.map((c, idx) => {
          const authority = c.authority_score
          const freshness = c.freshness_score
          const stale = typeof freshness === "number" && freshness < 0.6
          const lowAuth = typeof authority === "number" && authority < 0.7
          return (
            <li
              key={`${c.citation || c.source_name || "cite"}-${idx}`}
              className="rounded-lg border border-border/60 bg-muted/20 px-3 py-2 text-xs"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-medium text-foreground">
                  {c.citation || c.source_name || "Source"}
                </span>
                {typeof authority === "number" ? (
                  <ConfidenceBadge
                    score={authority}
                    isEstimate={Boolean(c.authority_is_estimate ?? c.confidence_is_estimate)}
                  />
                ) : null}
              </div>
              <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-muted-foreground">
                {c.jurisdiction ? <span>Jurisdiction: {c.jurisdiction}</span> : null}
                {c.effective_at || c.last_updated ? (
                  <span>Effective: {c.effective_at || c.last_updated}</span>
                ) : null}
                {c.license_type ? <span>License: {c.license_type}</span> : null}
                {typeof freshness === "number" ? (
                  <span>Freshness: {Math.round(freshness * 100)}%</span>
                ) : null}
              </div>
              {stale || lowAuth ? (
                <p className="mt-1 text-[11px] text-amber-700 dark:text-amber-400">
                  {stale && lowAuth
                    ? "Lower authority and stale — do not treat as equal to a current regulation."
                    : stale
                      ? "Stale source — verify current effective date before relying on this."
                      : "Lower authority than government / primary sources."}
                </p>
              ) : null}
              {c.web_link ? (
                <a
                  href={c.web_link}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 inline-block text-[11px] text-foreground underline"
                >
                  Open source
                </a>
              ) : null}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
