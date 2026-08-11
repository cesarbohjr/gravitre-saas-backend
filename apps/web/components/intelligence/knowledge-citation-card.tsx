"use client"

import { ConfidenceBadge } from "@/components/intelligence/confidence-badge"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

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
  /** Ingest honesty — e.g. curated_summary_live_html_blocked */
  content_mode?: string | null
  fetch_status?: {
    attempted?: boolean
    html_blocked?: boolean
    statuses?: Array<{ url?: string; status?: number | string }>
  } | null
}

function contentModeHonestyLabel(mode: string | null | undefined): string | null {
  if (!mode) return null
  if (mode === "curated_summary_live_html_blocked") {
    return "Curated summary — live source fetch was blocked"
  }
  if (mode.startsWith("curated_summary")) {
    return "Curated summary — not a live-fetched source page"
  }
  if (mode === "live_html" || mode === "live_fetched") {
    return null
  }
  // Unknown non-live modes still surface honestly
  if (mode !== "live") {
    return `Content mode: ${mode.replace(/_/g, " ")}`
  }
  return null
}

/** Module C — knowledge-pack citation provenance (authority + freshness + fetch honesty). */
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
          const honesty = contentModeHonestyLabel(c.content_mode)
          const blocked =
            c.content_mode === "curated_summary_live_html_blocked" ||
            Boolean(c.fetch_status?.html_blocked)
          return (
            <li
              key={`${c.citation || c.source_name || "cite"}-${idx}`}
              className={cn(
                "rounded-lg border px-3 py-2 text-xs",
                blocked
                  ? "border-warning/40 bg-warning/5"
                  : "border-border/60 bg-muted/20",
              )}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-medium text-foreground">
                  {c.citation || c.source_name || "Source"}
                </span>
                {typeof authority === "number" ? (
                  <ConfidenceBadge
                    score={authority}
                    isEstimate={Boolean(c.authority_is_estimate ?? c.confidence_is_estimate || blocked)}
                  />
                ) : null}
              </div>
              {honesty ? (
                <div className="mt-1.5">
                  <Badge
                    variant="outline"
                    className="border-warning/30 bg-warning/5 font-normal text-warning"
                  >
                    {honesty}
                  </Badge>
                </div>
              ) : null}
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
                <p className="mt-1 text-[11px] text-warning">
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
