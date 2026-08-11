"use client"

import useSWR from "swr"
import { Badge } from "@/components/ui/badge"
import { intelligenceApi, type KnowledgeFabricPackQuality } from "@/lib/api"
import { Books, WarningCircle } from "@phosphor-icons/react"
import { SectionCard } from "./shared"

function fmtPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—"
  return `${v}%`
}

function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v == null || Number.isNaN(v)) return "—"
  return Number.isInteger(v) ? String(v) : v.toFixed(digits)
}

function PackRow({ pack }: { pack: KnowledgeFabricPackQuality }) {
  const gaps = pack.gaps ?? []
  return (
    <tr className="border-b border-border/50 align-top last:border-0">
      <td className="px-3 py-2 font-medium text-foreground">{pack.pack_id.replace("pack.", "")}</td>
      <td className="px-3 py-2 tabular-nums">{pack.chunk_count}</td>
      <td className="px-3 py-2 tabular-nums">{fmtPct(pack.topic_coverage_pct)}</td>
      <td className="px-3 py-2 tabular-nums">
        {pack.authoritative_source_count}/{pack.primary_source_count}
      </td>
      <td className="px-3 py-2 tabular-nums">{fmtNum(pack.avg_authority_score, 3)}</td>
      <td className="px-3 py-2 tabular-nums">{fmtNum(pack.avg_freshness_days, 1)}</td>
      <td className="px-3 py-2 text-xs text-muted-foreground">
        {(pack.jurisdictions_covered || []).join(", ") || "—"}
      </td>
      <td className="px-3 py-2 tabular-nums">{pack.live_data_provider_count}</td>
      <td className="px-3 py-2 tabular-nums">{fmtPct(pack.citation_coverage_pct)}</td>
      <td className="px-3 py-2 tabular-nums">{fmtPct(pack.license_verified_pct)}</td>
      <td className="px-3 py-2 text-xs">
        {gaps.length === 0 ? (
          <span className="text-muted-foreground">none named</span>
        ) : (
          <ul className="space-y-0.5">
            {gaps.slice(0, 2).map((g) => (
              <li key={g} className="text-amber-700 dark:text-amber-300">
                {g}
              </li>
            ))}
          </ul>
        )}
      </td>
    </tr>
  )
}

export function KnowledgeFabricQualityCard() {
  const { data, isLoading, error } = useSWR(
    "knowledge-fabric/admin/quality",
    () => intelligenceApi.knowledgeFabricQuality(),
    { revalidateOnFocus: false },
  )

  const packs = data?.packs ?? []
  const gapCount = packs.reduce((n, p) => n + (p.gaps?.length || 0), 0)

  return (
    <SectionCard
      title="Knowledge Fabric quality"
      description="Exact live per-pack metrics — coverage, authority, freshness, jurisdictions, citation & license-verified % (no rounding up)"
      action={
        <Badge variant={gapCount > 0 ? "secondary" : "outline"} className="font-normal">
          {gapCount > 0 ? `${gapCount} gap signal${gapCount === 1 ? "" : "s"}` : "no named gaps"}
        </Badge>
      }
    >
      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading Knowledge Fabric quality…</p>
      ) : error ? (
        <p className="text-sm text-muted-foreground">
          Unable to load quality dashboard (platform admin required). Try refreshing.
        </p>
      ) : packs.length === 0 ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Books className="h-4 w-4" weight="duotone" aria-hidden />
          No pack metrics yet.
        </div>
      ) : (
        <div className="space-y-3">
          {data?.honesty ? (
            <p className="text-xs text-muted-foreground">
              Honesty: {data.honesty}
              {data.as_of ? ` · as of ${data.as_of}` : ""}
            </p>
          ) : null}
          {gapCount > 0 ? (
            <div
              role="status"
              className="flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2.5"
            >
              <WarningCircle
                className="mt-0.5 h-5 w-5 shrink-0 text-amber-700 dark:text-amber-300"
                weight="duotone"
                aria-hidden
              />
              <div className="min-w-0 space-y-1 text-xs text-muted-foreground">
                <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
                  Named coverage gaps (not an aggregate score)
                </p>
                <ul className="space-y-0.5">
                  {packs
                    .flatMap((p) => p.gaps)
                    .slice(0, 6)
                    .map((g) => (
                      <li key={g}>{g}</li>
                    ))}
                </ul>
              </div>
            </div>
          ) : null}
          <div className="overflow-x-auto rounded-xl border border-border/60">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-border/60 text-left text-xs text-muted-foreground">
                  <th className="px-3 py-2 font-medium">Pack</th>
                  <th className="px-3 py-2 font-medium">Chunks</th>
                  <th className="px-3 py-2 font-medium">Topic cov</th>
                  <th className="px-3 py-2 font-medium">Auth/prim</th>
                  <th className="px-3 py-2 font-medium">Avg auth</th>
                  <th className="px-3 py-2 font-medium">Fresh d</th>
                  <th className="px-3 py-2 font-medium">Jurisdictions</th>
                  <th className="px-3 py-2 font-medium">Live APIs</th>
                  <th className="px-3 py-2 font-medium">Cite %</th>
                  <th className="px-3 py-2 font-medium">Lic ver %</th>
                  <th className="px-3 py-2 font-medium">Gaps</th>
                </tr>
              </thead>
              <tbody>
                {packs.map((p) => (
                  <PackRow key={p.pack_id} pack={p} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </SectionCard>
  )
}
