"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { intelligenceApi, type KnowledgeFabricPackQuality } from "@/lib/api"
import { humanizeKnowledgeGap, packDisplayName } from "@/lib/learning-ui-copy"
import { Books, CaretDown, CaretUp, WarningCircle } from "@phosphor-icons/react"
import { SectionCard } from "./shared"
import { cn } from "@/lib/utils"

type HealthTone = "ready" | "watch" | "thin"

function packHealth(pack: KnowledgeFabricPackQuality): {
  tone: HealthTone
  label: string
  summary: string
} {
  const gaps = pack.gaps?.length ?? 0
  const topic = pack.topic_coverage_pct ?? 0
  const license = pack.license_verified_pct ?? 0
  if (gaps === 0 && topic >= 85 && license >= 80) {
    return {
      tone: "ready",
      label: "Ready",
      summary: "Solid topic coverage and verified sources for agent answers.",
    }
  }
  if (gaps >= 2 || topic < 50 || license < 50) {
    return {
      tone: "thin",
      label: "Needs attention",
      summary: "Agents in this area may answer with thinner grounding until coverage improves.",
    }
  }
  return {
    tone: "watch",
    label: "Watch",
    summary: "Usable, with a few named gaps worth improving when you can.",
  }
}

const TONE_STYLES: Record<HealthTone, string> = {
  ready: "border-emerald-500/25 bg-emerald-500/5",
  watch: "border-amber-500/25 bg-amber-500/5",
  thin: "border-rose-500/25 bg-rose-500/5",
}

const TONE_BADGE: Record<HealthTone, string> = {
  ready: "bg-emerald-500/15 text-emerald-800 dark:text-emerald-200",
  watch: "bg-amber-500/15 text-amber-900 dark:text-amber-200",
  thin: "bg-rose-500/15 text-rose-800 dark:text-rose-200",
}

function PackHealthCard({ pack }: { pack: KnowledgeFabricPackQuality }) {
  const health = packHealth(pack)
  const gaps = (pack.gaps ?? []).map(humanizeKnowledgeGap).filter(Boolean)
  const name = packDisplayName(pack.pack_id)

  return (
    <article className={cn("rounded-2xl border p-4 shadow-sm", TONE_STYLES[health.tone])}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold text-foreground">{name}</h3>
          <p className="mt-1 text-sm text-muted-foreground text-pretty">{health.summary}</p>
        </div>
        <Badge className={cn("font-normal hover:opacity-100", TONE_BADGE[health.tone])}>{health.label}</Badge>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div>
          <dt className="text-xs text-muted-foreground">Topic coverage</dt>
          <dd className="mt-0.5 text-sm font-semibold tabular-nums">
            {pack.topic_coverage_pct != null ? `${Math.round(pack.topic_coverage_pct)}%` : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Trusted sources</dt>
          <dd className="mt-0.5 text-sm font-semibold tabular-nums">
            {pack.authoritative_source_count}/{pack.primary_source_count}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">License-checked</dt>
          <dd className="mt-0.5 text-sm font-semibold tabular-nums">
            {pack.license_verified_pct != null ? `${Math.round(pack.license_verified_pct)}%` : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Knowledge pieces</dt>
          <dd className="mt-0.5 text-sm font-semibold tabular-nums">{pack.chunk_count}</dd>
        </div>
      </dl>

      {gaps.length > 0 ? (
        <ul className="mt-3 space-y-1 border-t border-border/50 pt-3 text-sm text-muted-foreground">
          {gaps.slice(0, 3).map((g) => (
            <li key={g} className="flex gap-2 text-pretty">
              <WarningCircle
                className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-300"
                weight="duotone"
                aria-hidden
              />
              <span>{g}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 border-t border-border/50 pt-3 text-sm text-muted-foreground">
          No named gaps for this area.
        </p>
      )}
    </article>
  )
}

export function KnowledgeFabricQualityCard() {
  const [showDetails, setShowDetails] = useState(false)
  const { data, isLoading, error } = useSWR(
    "knowledge-fabric/admin/quality",
    () => intelligenceApi.knowledgeFabricQuality(),
    { revalidateOnFocus: false },
  )

  const packs = data?.packs ?? []
  const ranked = useMemo(() => {
    const order: Record<HealthTone, number> = { thin: 0, watch: 1, ready: 2 }
    return [...packs].sort(
      (a, b) => order[packHealth(a).tone] - order[packHealth(b).tone] || a.pack_id.localeCompare(b.pack_id),
    )
  }, [packs])
  const attention = ranked.filter((p) => packHealth(p).tone !== "ready").length

  return (
    <SectionCard
      title="Knowledge readiness"
      description="How well Gravitre can ground agent answers in each business area — coverage and source trust, not a vanity score."
      action={
        packs.length > 0 ? (
          <Badge variant={attention > 0 ? "secondary" : "outline"} className="font-normal">
            {attention > 0
              ? `${attention} area${attention === 1 ? "" : "s"} need attention`
              : "All areas look ready"}
          </Badge>
        ) : null
      }
    >
      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading knowledge readiness…</p>
      ) : error ? (
        <p className="text-sm text-muted-foreground">
          Knowledge readiness is unavailable right now. Refresh, or check that you have admin access.
        </p>
      ) : packs.length === 0 ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Books className="h-4 w-4" weight="duotone" aria-hidden />
          No knowledge packs measured yet.
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-sm leading-relaxed text-muted-foreground text-pretty">
            Use this when deciding whether agents in Sales, Legal, or other packs have enough trusted material to
            answer confidently. Gaps mean thinner grounding — not that the product is broken.
          </p>

          <div className="grid gap-3 lg:grid-cols-2">
            {ranked.map((pack) => (
              <PackHealthCard key={pack.pack_id} pack={pack} />
            ))}
          </div>

          <div className="border-t border-border/60 pt-3">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="gap-1.5 px-2"
              onClick={() => setShowDetails((v) => !v)}
              aria-expanded={showDetails}
            >
              {showDetails ? (
                <CaretUp className="h-4 w-4" weight="bold" aria-hidden />
              ) : (
                <CaretDown className="h-4 w-4" weight="bold" aria-hidden />
              )}
              {showDetails ? "Hide technical metrics" : "Show technical metrics"}
            </Button>
            {showDetails ? (
              <div className="mt-3 overflow-x-auto rounded-xl border border-border/60">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-border/60 text-left text-xs text-muted-foreground">
                      <th className="px-3 py-2 font-medium">Area</th>
                      <th className="px-3 py-2 font-medium">Pieces</th>
                      <th className="px-3 py-2 font-medium">Topics</th>
                      <th className="px-3 py-2 font-medium">Authority</th>
                      <th className="px-3 py-2 font-medium">Freshness (days)</th>
                      <th className="px-3 py-2 font-medium">Regions</th>
                      <th className="px-3 py-2 font-medium">Citations</th>
                      <th className="px-3 py-2 font-medium">Licenses</th>
                    </tr>
                  </thead>
                  <tbody>
                    {packs.map((p) => (
                      <tr key={p.pack_id} className="border-b border-border/40 last:border-0">
                        <td className="px-3 py-2 font-medium">{packDisplayName(p.pack_id)}</td>
                        <td className="px-3 py-2 tabular-nums">{p.chunk_count}</td>
                        <td className="px-3 py-2 tabular-nums">
                          {p.topic_coverage_pct != null ? `${Math.round(p.topic_coverage_pct)}%` : "—"}
                        </td>
                        <td className="px-3 py-2 tabular-nums">
                          {p.authoritative_source_count}/{p.primary_source_count}
                        </td>
                        <td className="px-3 py-2 tabular-nums">
                          {p.avg_freshness_days != null ? p.avg_freshness_days.toFixed(1) : "—"}
                        </td>
                        <td className="px-3 py-2 text-xs text-muted-foreground">
                          {(p.jurisdictions_covered || []).join(", ") || "—"}
                        </td>
                        <td className="px-3 py-2 tabular-nums">
                          {p.citation_coverage_pct != null ? `${Math.round(p.citation_coverage_pct)}%` : "—"}
                        </td>
                        <td className="px-3 py-2 tabular-nums">
                          {p.license_verified_pct != null ? `${Math.round(p.license_verified_pct)}%` : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {data?.as_of ? (
                  <p className="border-t border-border/50 px-3 py-2 text-xs text-muted-foreground">
                    Snapshot updated {new Date(data.as_of).toLocaleString()}
                  </p>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      )}
    </SectionCard>
  )
}
