"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import {
  Brain,
  ChartLine,
  CircleHelp,
  Database,
  LayoutGrid,
  List,
  MessageSquareText,
  Network,
  Plus,
  Rocket,
  Search,
  Sparkles,
  Users,
  Wallet,
  Workflow,
  ArrowRight,
  type LucideIcon,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { cn } from "@/lib/utils"
import { APP_ROUTES } from "@/lib/app-routes"
import { formatScore, modelStatusChipClass } from "@/lib/intelligence/helpers"
import {
  BUILT_IN_MODEL_DOMAINS,
  domainLabel,
  statusShortLabel,
  statusTone,
  summarizeBrainHealth,
  type BuiltInModelDomainId,
  type BuiltInModelListItem,
} from "@/lib/built-in-model-catalog"

type FilterKey = "all" | "active" | "needs_data" | "roadmap"
type ViewMode = "directory" | "table"

const DOMAIN_ICONS: Record<BuiltInModelDomainId, LucideIcon> = {
  customer: Users,
  workflows: Workflow,
  search: Search,
  revenue: Wallet,
  support: MessageSquareText,
  learning: Brain,
  future: Sparkles,
}

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

function ModelCard({
  row,
  selected,
  onSelect,
}: {
  row: BuiltInModelListItem
  selected: boolean
  onSelect: () => void
}) {
  const tone = statusTone(row.status)
  const Icon = DOMAIN_ICONS[row.guide.domain] ?? Network
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "group flex h-full min-h-[188px] w-full flex-col rounded-xl border bg-card p-4 text-left transition",
        "hover:border-primary/35 hover:shadow-[0_8px_28px_-12px_color-mix(in_oklch,var(--primary)_35%,transparent)]",
        selected
          ? "border-primary/50 ring-2 ring-primary/20"
          : "border-border/70 shadow-sm",
      )}
    >
      <div className="flex items-start gap-3">
        <span
          className={cn(
            "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ring-1",
            tone === "ready" && "bg-primary/10 text-primary ring-primary/20",
            tone === "learning" && "bg-[oklch(0.95_0.02_250)] text-[oklch(0.45_0.16_250)] ring-[oklch(0.85_0.04_250)] dark:bg-[oklch(0.22_0.03_250)] dark:text-[oklch(0.85_0.08_250)] dark:ring-[oklch(0.35_0.04_250)]",
            (tone === "planned" || tone === "off") && "bg-muted text-muted-foreground ring-border/70",
          )}
        >
          <Icon className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <p className="truncate text-sm font-semibold tracking-tight text-foreground">{row.guide.label}</p>
            <span className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", toneDot(tone))} aria-hidden />
          </div>
          <p className="mt-0.5 font-mono text-[10px] text-muted-foreground">{row.id}</p>
        </div>
      </div>

      <p className="mt-3 line-clamp-3 flex-1 text-[13px] leading-relaxed text-muted-foreground">
        {row.guide.summary}
      </p>

      {row.sufficiency.value != null ? (
        <div className="mt-3 space-y-1">
          <div className="flex items-center justify-between text-[10px] text-muted-foreground">
            <span>Data gate</span>
            <span className="tabular-nums">{row.sufficiency.label}</span>
          </div>
          <Progress value={row.sufficiency.value} className="h-1" />
        </div>
      ) : null}

      <div className="mt-3 flex items-center justify-between gap-2 border-t border-border/60 pt-3">
        <p className="truncate text-[11px] text-muted-foreground">
          {domainLabel(row.guide.domain)}
          <span className="mx-1.5 text-border">·</span>
          {statusShortLabel(row.status)}
        </p>
        <Badge variant="outline" className={cn("h-5 shrink-0 px-1.5 text-[10px]", modelStatusChipClass(row.status))}>
          {statusShortLabel(row.status)}
        </Badge>
      </div>
    </button>
  )
}

function DetailPanel({ row }: { row: BuiltInModelListItem }) {
  const Icon = DOMAIN_ICONS[row.guide.domain] ?? Network
  const tone = statusTone(row.status)
  return (
    <motion.aside
      key={row.id}
      initial={{ opacity: 0, x: 8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.25 }}
      className="flex h-full flex-col rounded-xl border border-border/70 bg-card shadow-sm"
    >
      <div className="border-b border-border/60 p-5">
        <div className="flex items-start gap-3">
          <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/20">
            <Icon className="h-5 w-5" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-lg font-semibold tracking-tight text-foreground">{row.guide.label}</h3>
              <Badge variant="outline" className={cn("capitalize", modelStatusChipClass(row.status))}>
                {statusShortLabel(row.status)}
              </Badge>
            </div>
            <p className="mt-0.5 font-mono text-xs text-muted-foreground">{row.id}</p>
          </div>
        </div>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{row.guide.summary}</p>
      </div>

      <div className="space-y-4 p-5">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Why train it</p>
          <p className="mt-1.5 text-sm leading-relaxed text-foreground/90">{row.guide.whyItMatters}</p>
        </div>
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Data gate</p>
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
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-lg border border-border/60 bg-secondary/20 px-3 py-2">
            <p className="text-muted-foreground">Outcome score</p>
            <p className="mt-0.5 font-medium tabular-nums text-foreground">{formatScore(row.outcomeScore)}</p>
          </div>
          <div className="rounded-lg border border-border/60 bg-secondary/20 px-3 py-2">
            <p className="text-muted-foreground">Last trained</p>
            <p className="mt-0.5 font-medium text-foreground">{row.lastTrained === "—" ? "Not yet" : row.lastTrained}</p>
          </div>
        </div>
      </div>

      <div className="mt-auto flex flex-wrap gap-2 border-t border-border/60 p-4">
        <Button size="sm" asChild className="gap-1.5">
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
    </motion.aside>
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
  const [view, setView] = useState<ViewMode>("directory")
  const [query, setQuery] = useState("")
  const [domain, setDomain] = useState<BuiltInModelDomainId | "all">("all")
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const health = summarizeBrainHealth(items)
  const filtered = useMemo(() => filterItems(items, filter, query, domain), [items, filter, query, domain])

  useEffect(() => {
    if (selectedId && !filtered.some((r) => r.id === selectedId)) {
      setSelectedId(filtered[0]?.id ?? null)
    }
  }, [filtered, selectedId])

  const selected = filtered.find((r) => r.id === selectedId) ?? null
  const domainsInCatalog = useMemo(() => {
    const present = new Set(items.map((i) => i.guide.domain))
    return BUILT_IN_MODEL_DOMAINS.filter((d) => present.has(d.id))
  }, [items])

  return (
    <div className="space-y-5">
      {/* Compact brand header */}
      <section className="relative overflow-hidden rounded-2xl border border-border/70 bg-card">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-90"
          style={{
            background:
              "radial-gradient(ellipse 70% 80% at 0% 0%, color-mix(in oklch, var(--primary) 14%, transparent), transparent 55%), radial-gradient(ellipse 50% 60% at 100% 0%, color-mix(in oklch, oklch(0.55 0.16 250) 10%, transparent), transparent 50%)",
          }}
        />
        <div className="relative flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
          <div className="max-w-xl space-y-1.5">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">Org ML brain</p>
            <h2 className="text-xl font-semibold tracking-tight text-foreground">Built-in models</h2>
            <p className="text-sm text-muted-foreground">
              Uniform catalog of learners trained on your org signals. Select a model for why it matters and how to feed it.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="inline-flex items-center gap-1.5 rounded-md border border-primary/20 bg-primary/5 px-2.5 py-1.5 font-medium text-primary">
              <Brain className="h-3.5 w-3.5" />
              {health.trained} trained
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-md border border-[oklch(0.7_0.08_250)]/40 bg-[oklch(0.95_0.02_250)] px-2.5 py-1.5 font-medium text-[oklch(0.42_0.14_250)] dark:bg-[oklch(0.2_0.03_250)] dark:text-[oklch(0.85_0.06_250)]">
              <Sparkles className="h-3.5 w-3.5" />
              {health.learning} learning
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-md border border-border/70 bg-background/80 px-2.5 py-1.5 font-medium text-muted-foreground">
              <Database className="h-3.5 w-3.5" />
              {health.collecting} need data
            </span>
          </div>
        </div>
      </section>

      {/* Toolbar */}
      <div className="flex flex-col gap-3 rounded-xl border border-border/70 bg-card/80 p-3 sm:flex-row sm:items-center">
        <div className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search models, domains, or ids…"
            className="h-9 border-border/70 bg-background pl-8 text-sm"
          />
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {(
            [
              ["all", "All"],
              ["active", "Active"],
              ["needs_data", "Need data"],
              ["roadmap", "Roadmap"],
            ] as const
          ).map(([id, label]) => (
            <Button
              key={id}
              size="sm"
              variant={filter === id ? "default" : "ghost"}
              className="h-8 px-2.5 text-xs"
              onClick={() => onFilterChange?.(id)}
            >
              {label}
            </Button>
          ))}
          <span className="mx-1 hidden h-5 w-px bg-border sm:inline-block" />
          <Button
            size="sm"
            variant={view === "directory" ? "secondary" : "ghost"}
            className="h-8 w-8 p-0"
            aria-label="Directory view"
            onClick={() => setView("directory")}
          >
            <LayoutGrid className="h-3.5 w-3.5" />
          </Button>
          <Button
            size="sm"
            variant={view === "table" ? "secondary" : "ghost"}
            className="h-8 w-8 p-0"
            aria-label="Table view"
            onClick={() => setView("table")}
          >
            <List className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5">
        <Button
          size="sm"
          variant={domain === "all" ? "secondary" : "outline"}
          className="h-7 rounded-full px-3 text-[11px]"
          onClick={() => setDomain("all")}
        >
          All domains
        </Button>
        {domainsInCatalog.map((d) => {
          const Icon = DOMAIN_ICONS[d.id]
          return (
            <Button
              key={d.id}
              size="sm"
              variant={domain === d.id ? "secondary" : "outline"}
              className="h-7 gap-1.5 rounded-full px-3 text-[11px]"
              onClick={() => setDomain(d.id)}
            >
              <Icon className="h-3 w-3" />
              {d.title}
            </Button>
          )
        })}
      </div>

      {filtered.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border/70 px-4 py-10 text-center text-sm text-muted-foreground">
          No models match this filter.
        </p>
      ) : view === "table" ? (
        <div className="overflow-hidden rounded-xl border border-border/70 bg-card">
          <table className="min-w-full text-sm">
            <thead className="border-b border-border/70 bg-secondary/30 text-left text-[11px] uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">Model</th>
                <th className="px-4 py-3 font-medium">Domain</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Data gate</th>
                <th className="px-4 py-3 font-medium">Outcome</th>
                <th className="px-4 py-3 font-medium" />
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => {
                const tone = statusTone(row.status)
                return (
                  <tr
                    key={row.id}
                    className={cn(
                      "border-b border-border/50 last:border-0 transition hover:bg-secondary/20",
                      selectedId === row.id && "bg-primary/5",
                    )}
                  >
                    <td className="px-4 py-3">
                      <button type="button" className="text-left" onClick={() => setSelectedId(row.id)}>
                        <div className="flex items-center gap-2">
                          <span className={cn("h-2 w-2 rounded-full", toneDot(tone))} />
                          <span className="font-medium text-foreground">{row.guide.label}</span>
                        </div>
                        <p className="mt-0.5 font-mono text-[10px] text-muted-foreground">{row.id}</p>
                      </button>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{domainLabel(row.guide.domain)}</td>
                    <td className="px-4 py-3">
                      <Badge variant="outline" className={cn("text-[10px]", modelStatusChipClass(row.status))}>
                        {statusShortLabel(row.status)}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 tabular-nums text-muted-foreground">
                      {row.sufficiency.value == null ? "—" : row.sufficiency.label}
                    </td>
                    <td className="px-4 py-3 tabular-nums">{formatScore(row.outcomeScore)}</td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`${APP_ROUTES.builtInModels}/${encodeURIComponent(row.id)}`}
                        className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                      >
                        Open
                        <ArrowRight className="h-3 w-3" />
                      </Link>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
          {/* Equal-height directory — no per-domain orphan rows */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="grid auto-rows-fr gap-3 sm:grid-cols-2 xl:grid-cols-2 2xl:grid-cols-3"
          >
            {filtered.map((row) => (
              <ModelCard
                key={row.id}
                row={row}
                selected={selectedId === row.id}
                onSelect={() => setSelectedId(row.id === selectedId ? null : row.id)}
              />
            ))}
          </motion.div>

          <div className="xl:sticky xl:top-4 xl:self-start">
            {selected ? (
              <DetailPanel row={selected} />
            ) : (
              <div className="flex min-h-[320px] flex-col justify-between rounded-xl border border-dashed border-border/70 bg-secondary/15 p-5">
                <div className="space-y-3">
                  <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/20">
                    <ChartLine className="h-5 w-5" />
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-foreground">Select a model</p>
                    <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                      Click any card for a plain-language brief, data gate, and deep link — like an experiment
                      detail pane.
                    </p>
                  </div>
                  <div className="space-y-2 pt-1 text-xs text-muted-foreground">
                    <p className="flex gap-2">
                      <CircleHelp className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
                      Data bars are quality minimums, not caps you raise here.
                    </p>
                    <p className="flex gap-2">
                      <Plus className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
                      Custom models live in the production registry.
                    </p>
                  </div>
                </div>
                <div className="mt-6 flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" asChild className="gap-1.5">
                    <Link href={APP_ROUTES.models}>
                      <Rocket className="h-3.5 w-3.5" />
                      Model registry
                    </Link>
                  </Button>
                  <Button size="sm" variant="ghost" asChild>
                    <Link href={APP_ROUTES.training}>Training</Link>
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
