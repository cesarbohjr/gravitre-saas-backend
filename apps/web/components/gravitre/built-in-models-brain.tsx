"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import {
  ArrowRight,
  CircleHelp,
  Search,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { cn } from "@/lib/utils"
import { APP_ROUTES } from "@/lib/app-routes"
import { formatScore } from "@/lib/intelligence/helpers"
import { ModelStatusBadge } from "@/components/intelligence/model-status-badge"
import { TYPE } from "@/lib/design-system"
import {
  BUILT_IN_MODEL_DOMAINS,
  domainLabel,
  statusTone,
  summarizeBrainHealth,
  type BuiltInModelDomainId,
  type BuiltInModelListItem,
} from "@/lib/built-in-model-catalog"

type FilterKey = "all" | "active" | "needs_data" | "roadmap"

function toneDot(tone: ReturnType<typeof statusTone>): string {
  if (tone === "ready") return "bg-primary"
  if (tone === "learning") return "bg-[oklch(0.65_0.14_250)]"
  if (tone === "off") return "bg-muted-foreground/40"
  return "bg-muted-foreground/50"
}

function filterItems(items: BuiltInModelListItem[], filter: FilterKey, query: string, domain: BuiltInModelDomainId | "all") {
  const q = query.trim().toLowerCase()
  return items.filter((row) => {
    const tone = statusTone(row.status)
    if (filter === "active" && !(tone === "ready" || tone === "learning")) return false
    if (
      filter === "needs_data" &&
      !((tone === "ready" || tone === "learning") && row.sufficiency.value != null && row.sufficiency.value < 100)
    ) {
      return false
    }
    if (filter === "roadmap" && !(tone === "planned" || tone === "off")) return false
    if (domain !== "all" && row.guide.domain !== domain) return false
    if (!q) return true
    return (
      row.guide.label.toLowerCase().includes(q) ||
      row.id.toLowerCase().includes(q) ||
      row.guide.summary.toLowerCase().includes(q) ||
      domainLabel(row.guide.domain).toLowerCase().includes(q)
    )
  })
}

function DetailPanel({ row }: { row: BuiltInModelListItem }) {
  const tone = statusTone(row.status)
  return (
    <aside className="flex h-full flex-col" data-review-surface="models-inspect">
      <div className="border-b border-divide p-4">
        <h3 className="text-base font-medium tracking-tight text-foreground">{row.guide.label}</h3>
        <p className="mt-0.5 font-mono text-xs text-muted-foreground">{row.id}</p>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{row.guide.summary}</p>
        <ModelStatusBadge status={row.status} className="mt-3" />
      </div>

      <div className="space-y-4 p-4">
        <div>
          <p className={TYPE.eyebrow}>Why train it</p>
          <p className="mt-1.5 text-sm leading-relaxed text-foreground/90">{row.guide.whyItMatters}</p>
        </div>
        <div>
          <p className={TYPE.eyebrow}>Data gate</p>
          <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{row.guide.dataExplainer}</p>
          {row.sufficiency.value != null ? (
            <div className="mt-3 space-y-1.5">
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Progress toward minimum</span>
                <span className="tabular-nums">{row.sufficiency.label}</span>
              </div>
              <Progress value={row.sufficiency.value} className="h-1.5" />
              <p className="text-[11px] text-muted-foreground">
                Gate, not ceiling — more verified examples past this still improve quality.
              </p>
            </div>
          ) : (
            <p className="mt-2 text-xs text-muted-foreground">{row.sufficiency.label}</p>
          )}
          {row.guide.howToFeed ? (
            <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
              <span className="font-medium text-foreground">How to feed it: </span>
              {row.guide.howToFeed}
            </p>
          ) : null}
        </div>
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div>
            <p className="text-muted-foreground">Outcome score</p>
            <p className="mt-0.5 font-medium tabular-nums text-foreground">{formatScore(row.outcomeScore)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Last trained</p>
            <p className="mt-0.5 font-medium text-foreground">{row.lastTrained === "—" ? "Not yet" : row.lastTrained}</p>
          </div>
        </div>
      </div>

      <div className="mt-auto flex flex-wrap gap-2 border-t border-divide p-4">
        <Button size="sm" asChild className="gap-1.5" data-review-cta="open-model">
          <Link href={`${APP_ROUTES.builtInModels}/${encodeURIComponent(row.id)}`}>
            Open model
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </Button>
        {(tone === "planned" || tone === "off") && (
          <Button size="sm" variant="outline" asChild>
            <Link href={APP_ROUTES.models}>Add custom model</Link>
          </Button>
        )}
      </div>
    </aside>
  )
}

export function BuiltInModelsBrain({
  items,
  filter,
  onFilterChange,
}: {
  items: BuiltInModelListItem[]
  filter: FilterKey
  onFilterChange?: (filter: FilterKey) => void
}) {
  const [query, setQuery] = useState("")
  const [domain, setDomain] = useState<BuiltInModelDomainId | "all">("all")
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const health = summarizeBrainHealth(items)
  const filtered = useMemo(() => filterItems(items, filter, query, domain), [items, filter, query, domain])

  useEffect(() => {
    if (selectedId && !filtered.some((r) => r.id === selectedId)) {
      setSelectedId(null)
    }
  }, [filtered, selectedId])

  const selected = filtered.find((r) => r.id === selectedId) ?? null
  const domainsInCatalog = useMemo(() => {
    const present = new Set(items.map((i) => i.guide.domain))
    return BUILT_IN_MODEL_DOMAINS.filter((d) => present.has(d.id))
  }, [items])

  return (
    <div className="space-y-5">
      <section>
        <p className={TYPE.eyebrow}>Catalog</p>
        <h2 className="mt-1 text-lg font-semibold tracking-tight text-foreground">Built-in models</h2>
        <p className={cn(TYPE.meta, "mt-1")}>
          Learners trained on org signals. Select a row — inspector stays closed until then.
        </p>
        <p className={cn(TYPE.meta, "mt-2")}>
          {health.trained + health.learning} active · {health.learning} learning · {health.collecting} need data ·{" "}
          {health.planned} roadmap
        </p>
      </section>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search models, domains, or ids…"
            className="h-9 border-divide bg-background pl-8 text-sm"
          />
        </div>
        <nav aria-label="Built-in model filters" className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          {(
            [
              ["all", "All"],
              ["active", "Active"],
              ["needs_data", "Need data"],
              ["roadmap", "Roadmap"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={cn(
                TYPE.meta,
                "underline-offset-4",
                filter === id
                  ? "text-[color:var(--g-text-primary)] underline"
                  : "text-[color:var(--g-text-muted)] hover:text-[color:var(--g-text-primary)]",
              )}
              onClick={() => onFilterChange?.(id)}
            >
              {label}
            </button>
          ))}
        </nav>
      </div>

      <nav aria-label="Model domains" className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <button
          type="button"
          className={cn(
            TYPE.meta,
            "underline-offset-4",
            domain === "all"
              ? "text-[color:var(--g-text-primary)] underline"
              : "text-[color:var(--g-text-muted)] hover:text-[color:var(--g-text-primary)]",
          )}
          onClick={() => setDomain("all")}
        >
          All domains
        </button>
        {domainsInCatalog.map((d) => (
          <button
            key={d.id}
            type="button"
            className={cn(
              TYPE.meta,
              "underline-offset-4",
              domain === d.id
                ? "text-[color:var(--g-text-primary)] underline"
                : "text-[color:var(--g-text-muted)] hover:text-[color:var(--g-text-primary)]",
            )}
            onClick={() => setDomain(d.id)}
          >
            {d.title}
          </button>
        ))}
      </nav>

      {filtered.length === 0 ? (
        <p className="border border-dashed border-divide px-4 py-10 text-center text-sm text-muted-foreground">
          No models match this filter.
        </p>
      ) : (
        <div className="flex flex-col border border-divide lg:flex-row">
          <div className="min-w-0 flex-1 overflow-x-auto" data-review-surface="models-queue">
            <table className="min-w-full text-sm">
              <thead className="border-b border-divide text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">Model</th>
                  <th className="px-3 py-2 font-medium">Domain</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Data gate</th>
                  <th className="px-3 py-2 font-medium">Outcome</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => {
                  const tone = statusTone(row.status)
                  return (
                    <tr
                      key={row.id}
                      className={cn(
                        "border-b border-divide last:border-0",
                        selectedId === row.id && "bg-[color:var(--g-surface-2)]",
                      )}
                    >
                      <td className="px-3 py-2">
                        <button type="button" className="text-left" onClick={() => setSelectedId(row.id)}>
                          <div className="flex items-center gap-2">
                            <span className={cn("h-2 w-2 rounded-full", toneDot(tone))} />
                            <span className="font-medium text-foreground">{row.guide.label}</span>
                          </div>
                          <p className="mt-0.5 font-mono text-[10px] text-muted-foreground">{row.id}</p>
                        </button>
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">{domainLabel(row.guide.domain)}</td>
                      <td className="px-3 py-2">
                        <ModelStatusBadge status={row.status} size="sm" showDetail={false} />
                      </td>
                      <td className="px-3 py-2 tabular-nums text-muted-foreground">
                        {row.sufficiency.value == null ? "—" : row.sufficiency.label}
                      </td>
                      <td className="px-3 py-2 tabular-nums">{formatScore(row.outcomeScore)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          {selected ? (
            <div className="flex-1 border-t border-divide bg-[color:var(--g-canvas)] lg:border-t-0 lg:border-l">
              <DetailPanel row={selected} />
            </div>
          ) : (
            <p className="sr-only">Select a model — inspector stays closed until then.</p>
          )}
        </div>
      )}

      <p className={cn(TYPE.meta, "flex items-start gap-2")}>
        <CircleHelp className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
        Data bars are quality minimums, not caps. Custom models live in the production registry.
      </p>
    </div>
  )
}
