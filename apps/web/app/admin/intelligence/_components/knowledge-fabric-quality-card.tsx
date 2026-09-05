"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { intelligenceApi, type KnowledgeFabricPackQuality } from "@/lib/api"
import {
  departmentDisplayName,
  humanizeKnowledgeGap,
  knowledgePackDepartment,
  knowledgePackKind,
  packDisplayName,
  type KnowledgePackKind,
} from "@/lib/learning-ui-copy"
import { Books, CaretDown, CaretUp, Plugs, WarningCircle } from "@phosphor-icons/react"
import { SectionCard } from "./shared"
import { cn } from "@/lib/utils"
import { RADIUS, STATUS } from "@/lib/design-system"

type HealthTone = "ready" | "watch" | "thin"

const PAGE_SIZE = 6

function packHealth(pack: KnowledgeFabricPackQuality): {
  tone: HealthTone
  label: string
  summary: string
} {
  const gaps = pack.gaps?.length ?? 0
  const topic = pack.topic_coverage_pct ?? 0
  const license = pack.license_verified_pct ?? 0
  const isTool = knowledgePackKind(pack.pack_id) === "tool"
  if (gaps === 0 && topic >= 85 && license >= 80) {
    return {
      tone: "ready",
      label: "Ready",
      summary: isTool
        ? "Solid connector guidance for agent tool use."
        : "Solid topic coverage and verified sources.",
    }
  }
  if (gaps >= 2 || topic < 50 || license < 50) {
    return {
      tone: "thin",
      label: "Needs attention",
      summary: isTool
        ? "Thin tool guidance. Agents may struggle with this connector."
        : "Thin grounding until coverage improves.",
    }
  }
  return {
    tone: "watch",
    label: "Watch",
    summary: isTool
      ? "Usable tool knowledge with a few gaps."
      : "Usable, with a few named gaps to improve.",
  }
}

const TONE_STYLES: Record<HealthTone, string> = {
  ready: STATUS.verified,
  watch: STATUS.pending,
  thin: STATUS.failed,
}

const TONE_BADGE: Record<HealthTone, string> = {
  ready: STATUS.verified,
  watch: STATUS.pending,
  thin: STATUS.failed,
}

function PackHealthCard({ pack }: { pack: KnowledgeFabricPackQuality }) {
  const health = packHealth(pack)
  const gaps = (pack.gaps ?? []).map(humanizeKnowledgeGap).filter(Boolean)
  const name = packDisplayName(pack.pack_id)
  const kind = knowledgePackKind(pack.pack_id)
  const isTool = kind === "tool"
  const department = knowledgePackDepartment(pack.pack_id)

  return (
    <article className={cn("border p-4 shadow-sm", RADIUS.panel, TONE_STYLES[health.tone])}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold text-foreground">{name}</h3>
            <Badge variant="outline" className="font-normal">
              {isTool ? (
                <span className="inline-flex items-center gap-1">
                  <Plugs className="h-3.5 w-3.5" weight="duotone" aria-hidden />
                  Tool knowledge
                </span>
              ) : (
                <span className="inline-flex items-center gap-1">
                  <Books className="h-3.5 w-3.5" weight="duotone" aria-hidden />
                  Topic knowledge
                </span>
              )}
            </Badge>
          </div>
          {!isTool && department ? (
            <p className="mt-1 text-xs text-muted-foreground">{departmentDisplayName(department)}</p>
          ) : null}
          <p className="mt-1 text-sm text-muted-foreground text-pretty">{health.summary}</p>
        </div>
        <Badge className={cn("font-normal hover:opacity-100", TONE_BADGE[health.tone])}>{health.label}</Badge>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div>
          <dt className="text-xs text-muted-foreground">{isTool ? "Practice coverage" : "Topic coverage"}</dt>
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
        <p className="mt-3 border-t border-border/50 pt-3 text-sm text-muted-foreground">No named gaps.</p>
      )}
    </article>
  )
}

export function KnowledgeFabricQualityCard() {
  const [showDetails, setShowDetails] = useState(false)
  const [kind, setKind] = useState<KnowledgePackKind | "all">("topic")
  const [department, setDepartment] = useState<string>("all")
  const [page, setPage] = useState(0)

  const { data, isLoading, error } = useSWR(
    "knowledge-fabric/admin/quality",
    () => intelligenceApi.knowledgeFabricQuality(),
    { revalidateOnFocus: false },
  )

  const packs = data?.packs ?? []

  const topicCount = useMemo(() => packs.filter((p) => knowledgePackKind(p.pack_id) === "topic").length, [packs])
  const toolCount = useMemo(() => packs.filter((p) => knowledgePackKind(p.pack_id) === "tool").length, [packs])

  const departments = useMemo(() => {
    const set = new Set<string>()
    for (const p of packs) {
      const d = knowledgePackDepartment(p.pack_id)
      if (d) set.add(d)
    }
    return Array.from(set).sort((a, b) => departmentDisplayName(a).localeCompare(departmentDisplayName(b)))
  }, [packs])

  const filtered = useMemo(() => {
    const order: Record<HealthTone, number> = { thin: 0, watch: 1, ready: 2 }
    return [...packs]
      .filter((p) => {
        const k = knowledgePackKind(p.pack_id)
        if (kind !== "all" && k !== kind) return false
        if (kind === "topic" || kind === "all") {
          if (department !== "all" && k === "topic") {
            return knowledgePackDepartment(p.pack_id) === department
          }
        }
        return true
      })
      .sort(
        (a, b) => order[packHealth(a).tone] - order[packHealth(b).tone] || a.pack_id.localeCompare(b.pack_id),
      )
  }, [packs, kind, department])

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const safePage = Math.min(page, pageCount - 1)
  const pageItems = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE)
  const attention = filtered.filter((p) => packHealth(p).tone !== "ready").length

  return (
    <SectionCard
      title="Knowledge readiness"
      description="Trusted material for agent answers by department topic or connected tool."
      action={
        packs.length > 0 ? (
          <Badge variant={attention > 0 ? "secondary" : "outline"} className="font-normal">
            {attention > 0
              ? `${attention} need${attention === 1 ? "s" : ""} attention`
              : "Looking ready"}
          </Badge>
        ) : null
      }
    >
      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading knowledge readiness…</p>
      ) : error ? (
        <p className="text-sm text-muted-foreground">
          Knowledge readiness unavailable. Refresh or check admin access.
        </p>
      ) : packs.length === 0 ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Books className="h-4 w-4" weight="duotone" aria-hidden />
          No knowledge packs measured yet.
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
            <div
              className="inline-flex rounded-lg border border-border/70 bg-secondary/30 p-1"
              role="group"
              aria-label="Knowledge type"
            >
              {(
                [
                  { value: "topic" as const, label: "Topics", count: topicCount },
                  { value: "tool" as const, label: "Tools", count: toolCount },
                  { value: "all" as const, label: "All", count: packs.length },
                ] as const
              ).map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => {
                    setKind(opt.value)
                    setPage(0)
                    if (opt.value === "tool") setDepartment("all")
                  }}
                  className={cn(
                    "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                    kind === opt.value
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {opt.label}
                  <span className="ml-1 tabular-nums text-muted-foreground">({opt.count})</span>
                </button>
              ))}
            </div>

            {kind !== "tool" ? (
              <Select
                value={department}
                onValueChange={(v) => {
                  setDepartment(v)
                  setPage(0)
                }}
              >
                <SelectTrigger className="w-full sm:w-[14rem]" aria-label="Filter by department">
                  <SelectValue placeholder="Department" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All departments</SelectItem>
                  {departments.map((d) => (
                    <SelectItem key={d} value={d}>
                      {departmentDisplayName(d)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : null}

            <p className="text-xs text-muted-foreground sm:ml-auto tabular-nums">
              Showing {filtered.length}
              {kind === "topic" ? " topic" : kind === "tool" ? " tool" : ""} area
              {filtered.length === 1 ? "" : "s"}
            </p>
          </div>

          <p className="text-sm leading-relaxed text-muted-foreground text-pretty">
            {kind === "tool"
              ? "Tool knowledge covers how agents use connected products (HubSpot, Stripe, and so on)."
              : kind === "topic"
                ? "Topic knowledge covers department subjects such as Legal, Sales, or Finance."
                : "Topics are department subjects. Tools are connector practice guides."}
          </p>

          {pageItems.length > 0 ? (
            <div className="grid gap-3 lg:grid-cols-2">
              {pageItems.map((pack) => (
                <PackHealthCard key={pack.pack_id} pack={pack} />
              ))}
            </div>
          ) : (
            <p className="rounded-xl border border-dashed border-border/70 px-4 py-8 text-center text-sm text-muted-foreground">
              Nothing matches this filter.
            </p>
          )}

          {pageCount > 1 ? (
            <div className="flex items-center justify-between gap-2">
              <Button
                size="sm"
                variant="outline"
                disabled={safePage <= 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
              >
                Previous
              </Button>
              <span className="text-xs text-muted-foreground tabular-nums">
                Page {safePage + 1} of {pageCount}
              </span>
              <Button
                size="sm"
                variant="outline"
                disabled={safePage >= pageCount - 1}
                onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
              >
                Next
              </Button>
            </div>
          ) : null}

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
                      <th className="px-3 py-2 font-medium">Type</th>
                      <th className="px-3 py-2 font-medium">Area</th>
                      <th className="px-3 py-2 font-medium">Pieces</th>
                      <th className="px-3 py-2 font-medium">Coverage</th>
                      <th className="px-3 py-2 font-medium">Authority</th>
                      <th className="px-3 py-2 font-medium">Freshness (days)</th>
                      <th className="px-3 py-2 font-medium">Licenses</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((p) => (
                      <tr key={p.pack_id} className="border-b border-border/40 last:border-0">
                        <td className="px-3 py-2 text-xs text-muted-foreground">
                          {knowledgePackKind(p.pack_id) === "tool" ? "Tool" : "Topic"}
                        </td>
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
