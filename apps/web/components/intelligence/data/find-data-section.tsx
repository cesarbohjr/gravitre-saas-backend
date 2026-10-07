"use client"

/**
 * "Find the right data": one search across the org's own training datasets and
 * every public catalog the backend registers (Hugging Face, Kaggle, …). Results
 * are ranked by how well their metadata matches the request, previewed against
 * the org's knowledge entities, then saved as a training reference for a model.
 * Only provider metadata is read; nothing is downloaded.
 */
import { useMemo, useRef, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { AlertCircle, Check, Lock, Sparkles } from "lucide-react"
import { Button } from "@/components/ui/button"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { trainingApi, type ExternalDatasetSummary } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import { TYPE } from "@/lib/design-system"
import { datasetTypeMeta } from "@/lib/training-ui-copy"
import { cn } from "@/lib/utils"
import type { TrainingDataset } from "@/types/api"
import {
  computeFit,
  entityLabel,
  externalHaystack,
  fitBasis,
  mapFieldToEntity,
  ownHaystack,
  readableTags,
  reportedFields,
  reportedLicense,
  searchTerms,
  type Fit,
} from "./data-match"
import type { DataSources } from "./use-data-sources"
import { UseForDialog } from "./use-for-dialog"
import { formatShortDate } from "./format"

const YOUR_DATA = "yours"
/** Field names of the org's own material: example and feedback records (TrainingRecord) or uploaded documents. */
const ownFields = (dataset: TrainingDataset) =>
  dataset.type === "documents" ? ["title", "content"] : ["input", "expected_output"]

type Match =
  | {
      key: string
      kind: "own"
      label: string
      description: string
      tags: string[]
      fit: Fit
      restricted: false
      dataset: TrainingDataset
      order: number
    }
  | {
      key: string
      kind: "external"
      providerId: string
      providerLabel: string
      label: string
      description: string
      tags: string[]
      fit: Fit
      restricted: boolean
      dataset: ExternalDatasetSummary
      order: number
    }

type ProviderResult = { providerId: string; datasets: ExternalDatasetSummary[]; error: string | null }

export function FindDataSection({
  enabled,
  sources,
  onManageDataset,
}: {
  enabled: boolean
  sources: DataSources
  /** Opens the dataset editor below with this dataset. */
  onManageDataset: (datasetId: string) => void
}) {
  const providers = useMemo(() => sources.providers.data?.providers ?? [], [sources.providers.data])
  const providerLabel = (id: string) => providers.find((p) => p.id === id)?.label ?? id
  const [query, setQuery] = useState("")
  const [term, setTerm] = useState("")
  const [chosen, setChosen] = useState<string[] | null>(null)
  // Default: your data plus the first public catalog, as the design shows.
  const activeSources = chosen ?? [YOUR_DATA, ...(providers[0] ? [providers[0].id] : [])]
  const activeProviders = providers.map((p) => p.id).filter((id) => activeSources.includes(id))
  const searchYours = activeSources.includes(YOUR_DATA)

  function toggleSource(id: string) {
    const next = activeSources.includes(id) ? activeSources.filter((s) => s !== id) : [...activeSources, id]
    setChosen(next)
  }

  const search = useSWR(
    enabled && term && activeProviders.length > 0 ? ["data-find", term, ...activeProviders] : null,
    async (): Promise<ProviderResult[]> => {
      const settled = await Promise.allSettled(
        activeProviders.map((id) => trainingApi.searchExternalDatasets(id, term, 12)),
      )
      return settled.map((result, index) => ({
        providerId: activeProviders[index],
        datasets: result.status === "fulfilled" ? result.value.datasets ?? [] : [],
        error: result.status === "rejected" ? "Search failed" : null,
      }))
    },
    { revalidateOnFocus: false },
  )

  const terms = useMemo(() => searchTerms(term), [term])
  const matches = useMemo<Match[]>(() => {
    if (!term) return []
    const out: Match[] = []
    let order = 0
    if (searchYours) {
      for (const dataset of sources.datasets.data?.datasets ?? []) {
        const fit = computeFit(terms, ownHaystack(dataset))
        if (fit.matched === 0) continue
        out.push({
          key: `own:${dataset.id}`,
          kind: "own",
          label: dataset.name,
          description: dataset.description || datasetTypeMeta(dataset.type).summary,
          tags: [datasetTypeMeta(dataset.type).label, `${dataset.record_count} record${dataset.record_count === 1 ? "" : "s"}`],
          fit,
          restricted: false,
          dataset,
          order: order++,
        })
      }
    }
    for (const result of search.data ?? []) {
      for (const dataset of result.datasets) {
        out.push({
          key: `${result.providerId}:${dataset.dataset_id}`,
          kind: "external",
          providerId: result.providerId,
          providerLabel: providerLabel(result.providerId),
          label: dataset.dataset_id,
          description: dataset.description || "No description reported.",
          tags: readableTags(dataset.tags),
          fit: computeFit(terms, externalHaystack(dataset)),
          restricted: dataset.gated || dataset.private,
          dataset,
          order: order++,
        })
      }
    }
    return out.sort((a, b) => {
      if (a.restricted !== b.restricted) return a.restricted ? 1 : -1
      const ratio = (m: Match) => (m.fit.total ? m.fit.matched / m.fit.total : 0)
      return ratio(b) - ratio(a) || a.order - b.order
    })
    // providerLabel is derived from providers.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [term, terms, searchYours, sources.datasets.data, search.data, providers])

  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const selected = matches.find((m) => m.key === selectedKey && !m.restricted) ?? matches.find((m) => !m.restricted) ?? null

  // Train-for target: the org's real models, then agents.
  const models = useMemo(() => sources.mlModels.data?.models ?? [], [sources.mlModels.data])
  const agents = useMemo(() => sources.agents.data?.agents ?? [], [sources.agents.data])
  const targets = useMemo(
    () => [
      ...models.map((m) => ({ value: `model:${m.id}`, type: "model" as const, id: m.id, label: m.name || "Untitled model" })),
      ...agents.map((a) => ({ value: `agent:${a.id}`, type: "agent" as const, id: String(a.id), label: a.name || a.role || "Untitled agent" })),
    ],
    [models, agents],
  )
  const [targetValue, setTargetValue] = useState("")
  const target = targets.find((t) => t.value === targetValue) ?? targets[0] ?? null
  const targetsLoading = sources.mlModels.isLoading || sources.agents.isLoading

  const providerErrors = (search.data ?? []).filter((r) => r.error)
  const searching = Boolean(term) && search.isLoading

  return (
    <div className="space-y-6">
      <section
        aria-labelledby="find-data-heading"
        className="rounded-[var(--g-radius-panel)] bg-[color:var(--g-carbon)] px-5 py-6 text-[color:var(--g-bone)] sm:px-7 sm:py-7"
      >
        <div className="flex items-center gap-2.5">
          <Sparkles aria-hidden className="h-[18px] w-[18px] text-[color:var(--g-brand)]" />
          <h2 id="find-data-heading" className="text-lg font-semibold tracking-[-0.015em]">
            Find the right data
          </h2>
        </div>
        <p className="mt-2 text-sm text-[color:var(--g-bone)]/70">
          Describe what you want Gravitre to learn. It searches your data and public catalogs, then ranks each dataset by fit.
        </p>
        <form
          className="mt-5"
          onSubmit={(event) => {
            event.preventDefault()
            setTerm(query.trim())
            setSelectedKey(null)
          }}
        >
          <label htmlFor="data-intent" className="sr-only">
            What should Gravitre learn?
          </label>
          <div className="flex flex-col gap-2 rounded-[var(--g-radius-card)] border border-white/12 bg-white/[0.04] p-1.5 sm:flex-row sm:items-center">
            <input
              id="data-intent"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="What should Gravitre learn? For example, route support tickets to the right queue"
              className="min-h-11 min-w-0 flex-1 bg-transparent px-3 text-[15px] text-[color:var(--g-bone)] outline-none placeholder:text-[color:var(--g-bone)]/40"
            />
            <button
              type="submit"
              disabled={!query.trim() || activeSources.length === 0}
              className="min-h-11 rounded-[var(--g-radius-control)] bg-[color:var(--g-brand)] px-5 text-sm font-semibold text-[color:var(--g-carbon)] transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--g-brand)] focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--g-carbon)]"
            >
              Search
            </button>
          </div>
        </form>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="mr-1 text-xs text-[color:var(--g-bone)]/60">Search in</span>
          {[{ id: YOUR_DATA, label: "Your data" }, ...providers.map((p) => ({ id: p.id, label: p.label }))].map((source) => {
            const on = activeSources.includes(source.id)
            return (
              <button
                key={source.id}
                type="button"
                aria-pressed={on}
                onClick={() => toggleSource(source.id)}
                className={cn(
                  "inline-flex min-h-9 items-center gap-1.5 rounded-full border px-3 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--g-brand)]",
                  on
                    ? "border-[color:var(--g-brand)]/40 bg-[color:var(--g-brand)]/15 text-[color:var(--g-bone)]"
                    : "border-white/15 text-[color:var(--g-bone)]/70 hover:text-[color:var(--g-bone)]",
                )}
              >
                {on ? <Check aria-hidden className="h-3 w-3 text-[color:var(--g-brand)]" /> : null}
                {source.label}
              </button>
            )
          })}
          {sources.providers.error ? (
            <span className="text-xs text-[color:var(--g-bone)]/60">Public catalogs unavailable</span>
          ) : sources.providers.isLoading ? (
            <span className="text-xs text-[color:var(--g-bone)]/60">Loading catalogs…</span>
          ) : null}
          <span className="ml-auto text-xs text-[color:var(--g-bone)]/50">Only metadata is read until you import</span>
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)] lg:items-start">
        <section
          aria-labelledby="data-matches-heading"
          className="overflow-hidden rounded-[var(--g-radius-card)] border border-[color:var(--g-border-subtle)] bg-card"
        >
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--g-border-subtle)] px-5 py-4">
            <h2 id="data-matches-heading" className={TYPE.cardTitle}>
              {term ? (searching ? "Searching…" : `${matches.length} match${matches.length === 1 ? "" : "es"}`) : "Matches"}
            </h2>
            <label className="flex items-center gap-1.5 text-xs text-[color:var(--g-text-muted)]">
              Import to train
              <select
                aria-label="Import to train"
                value={target?.value ?? ""}
                onChange={(event) => setTargetValue(event.target.value)}
                disabled={targets.length === 0}
                title="Choose which model or agent an imported dataset trains"
                className="max-w-[12rem] cursor-pointer appearance-none truncate rounded-[var(--g-radius-control)] border-0 bg-transparent p-0 text-xs font-medium text-[color:var(--g-text-primary)] underline-offset-2 outline-none hover:underline focus-visible:ring-2 focus-visible:ring-[color:var(--g-brand)] disabled:cursor-default disabled:no-underline"
              >
                {targets.length === 0 ? (
                  <option value="">{targetsLoading ? "Loading…" : "No models or agents yet"}</option>
                ) : null}
                {models.length > 0 ? (
                  <optgroup label="Models">
                    {targets.filter((t) => t.type === "model").map((t) => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </optgroup>
                ) : null}
                {agents.length > 0 ? (
                  <optgroup label="Agents">
                    {targets.filter((t) => t.type === "agent").map((t) => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </optgroup>
                ) : null}
              </select>
            </label>
          </div>

          {!term ? (
            <p className={cn(TYPE.bodyMuted, "px-5 py-8")}>
              Describe what Gravitre should learn, then search. Matches from your data and public catalogs appear here.
            </p>
          ) : searching ? (
            <p role="status" className={cn(TYPE.bodyMuted, "px-5 py-8")}>
              Reading catalog metadata…
            </p>
          ) : search.error ? (
            <WorkSectionErrorCard title="Could not search datasets" message="Try again to search public catalogs." onRetry={() => void search.mutate()} />
          ) : matches.length === 0 ? (
            <p className={cn(TYPE.bodyMuted, "px-5 py-8")}>
              No matching datasets. Try different words or search more sources.
            </p>
          ) : (
            <ul className="divide-y divide-[color:var(--g-border-subtle)]">
              {matches.map((match) => (
                <li key={match.key}>
                  {match.restricted ? (
                    <div className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                      <div className="min-w-0">
                        <p className="flex items-center gap-1.5 font-mono text-[13px] text-[color:var(--g-text-secondary)]">
                          <Lock aria-hidden className="h-3.5 w-3.5 shrink-0" />
                          <span className="truncate">{match.label}</span>
                        </p>
                        <p className={cn(TYPE.meta, "mt-1")}>Restricted. The owner must approve access first.</p>
                      </div>
                      {match.kind === "external" && match.dataset.reference_url ? (
                        <Button asChild variant="outline" size="sm" className="min-h-11 shrink-0">
                          <a href={match.dataset.reference_url} target="_blank" rel="noreferrer">
                            Request access
                          </a>
                        </Button>
                      ) : null}
                    </div>
                  ) : (
                    <button
                      type="button"
                      aria-pressed={selected?.key === match.key}
                      onClick={() => setSelectedKey(match.key)}
                      className={cn(
                        "grid w-full gap-3 px-5 py-4 text-left transition-colors sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[color:var(--g-brand)]",
                        selected?.key === match.key ? "bg-[color:var(--g-brand-surface)]" : "hover:bg-[color:var(--g-surface-2)]",
                      )}
                    >
                      <span className="min-w-0">
                        <span className="block truncate font-mono text-[13px] font-medium text-[color:var(--g-text-primary)]">{match.label}</span>
                        <span className={cn(TYPE.meta, "mt-1 block line-clamp-2 text-[13px]")}>{match.description}</span>
                        <span className="mt-2 flex flex-wrap gap-1.5">
                          <span className="rounded-[4px] bg-[color:var(--g-approval-surface)] px-1.5 py-0.5 text-[11px] font-medium text-[color:var(--g-approval)]">
                            {match.kind === "own" ? "Your data" : match.providerLabel}
                          </span>
                          {match.tags.map((tag) => (
                            <span key={tag} className="rounded-[4px] bg-[color:var(--g-surface-2)] px-1.5 py-0.5 text-[11px] text-[color:var(--g-text-secondary)]">
                              {tag}
                            </span>
                          ))}
                        </span>
                      </span>
                      <FitMeter fit={match.fit} />
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
          {providerErrors.length > 0 ? (
            <p className={cn(TYPE.meta, "flex items-center gap-1.5 border-t border-[color:var(--g-border-subtle)] px-5 py-3")}>
              <AlertCircle aria-hidden className="h-3.5 w-3.5 text-[color:var(--g-warning)]" />
              {providerErrors.map((r) => providerLabel(r.providerId)).join(" and ")} could not be searched.
              <button type="button" className="font-medium text-[color:var(--g-brand-active)] hover:underline" onClick={() => void search.mutate()}>
                Try again
              </button>
            </p>
          ) : null}
        </section>

        <PreviewPanel
          enabled={enabled}
          match={selected}
          sources={sources}
          target={target}
          onManageDataset={onManageDataset}
        />
      </div>
    </div>
  )
}

function FitMeter({ fit }: { fit: Fit }) {
  const basis = fitBasis(fit)
  return (
    <span className="flex shrink-0 flex-row items-center gap-2 sm:flex-col sm:items-end" title={basis}>
      <span
        className={cn(
          "text-xs font-semibold",
          fit.level === "strong" ? "text-[color:var(--g-brand-active)]" : "text-[color:var(--g-text-primary)]",
        )}
      >
        {fit.label}
      </span>
      <span className="flex gap-1" role="img" aria-label={`${fit.label}. ${basis}.`}>
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className={cn(
              "h-1.5 w-3.5 rounded-full",
              i < fit.bars ? "bg-[color:var(--g-brand-active)]" : "bg-[color:var(--g-border-default)]",
            )}
          />
        ))}
      </span>
    </span>
  )
}

type Target = { value: string; type: "model" | "agent"; id: string; label: string } | null

function PreviewPanel({
  enabled,
  match,
  sources,
  target,
  onManageDataset,
}: {
  enabled: boolean
  match: Match | null
  sources: DataSources
  target: Target
  onManageDataset: (datasetId: string) => void
}) {
  const external = match?.kind === "external" ? match : null
  const inspect = useSWR(
    enabled && external ? ["external-dataset-inspect", external.providerId, external.dataset.dataset_id] : null,
    () => trainingApi.inspectExternalDataset(external!.providerId, external!.dataset.dataset_id),
    { revalidateOnFocus: false },
  )
  const entityTypes = sources.knowledgeGraph.data?.entity_types ?? []
  const saveLock = useRef(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [savedFor, setSavedFor] = useState<string | null>(null)
  const [useForOpen, setUseForOpen] = useState(false)
  const [lastKey, setLastKey] = useState<string | null>(null)
  if ((match?.key ?? null) !== lastKey) {
    setLastKey(match?.key ?? null)
    setSaveError(null)
    setSavedFor(null)
  }

  const shell = "rounded-[var(--g-radius-card)] border border-[color:var(--g-border-subtle)] bg-card px-5 py-5"

  if (!match) {
    return (
      <section aria-labelledby="data-preview-heading" className={shell}>
        <p className={TYPE.eyebrow}>Preview</p>
        <h2 id="data-preview-heading" className={cn(TYPE.cardTitle, "mt-1")}>
          Nothing selected
        </h2>
        <p className={cn(TYPE.bodyMuted, "mt-2")}>
          Pick a match to see how it maps to your knowledge and what to check before importing.
        </p>
      </section>
    )
  }

  if (match.kind === "own") {
    const dataset = match.dataset
    const meta = datasetTypeMeta(dataset.type)
    return (
      <section aria-labelledby="data-preview-heading" className={shell}>
        <p className={TYPE.eyebrow}>Preview</p>
        <h2 id="data-preview-heading" className="mt-1 break-all font-mono text-[15px] font-medium text-[color:var(--g-text-primary)]">
          {dataset.name}
        </h2>
        <KnowledgeMapping
          fields={ownFields(dataset)}
          entityTypes={entityTypes}
          noFieldsNote=""
        />
        <div className="mt-5 space-y-2">
          <p className="text-[13px] font-semibold text-[color:var(--g-text-primary)]">Checks before import</p>
          <ul className="space-y-1.5">
            <CheckRow ok>Already in Gravitre as a {meta.label.toLowerCase()} dataset</CheckRow>
            <CheckRow ok={dataset.record_count > 0}>
              {dataset.record_count > 0
                ? `${dataset.record_count} record${dataset.record_count === 1 ? "" : "s"} ready`
                : "No records yet. Add examples before training"}
            </CheckRow>
            <CheckRow ok={dataset.status === "ready"}>
              {dataset.status === "ready" ? `Updated ${formatShortDate(dataset.updated_at || dataset.created_at)}` : `Status: ${dataset.status}`}
            </CheckRow>
          </ul>
        </div>
        <div className="mt-6 flex flex-col gap-2 border-t border-[color:var(--g-border-subtle)] pt-5 sm:flex-row">
          <Button variant="brand" className="min-h-11 flex-1" onClick={() => onManageDataset(dataset.id)}>
            Train with this dataset
          </Button>
          <Button
            variant="outline"
            className="min-h-11"
            disabled
            title="Linking your own datasets to an agent or Play isn't available on this page yet."
          >
            Use for…
          </Button>
        </div>
      </section>
    )
  }

  const details = inspect.data?.dataset
  const fields = reportedFields(details?.cardData)
  const mappedCount = fields.filter((field) => mapFieldToEntity(field, entityTypes)).length
  const license = reportedLicense(details as unknown as Record<string, unknown> | undefined)
  const isPublic = details ? !details.private && !details.gated : !match.restricted

  async function importForTarget() {
    if (!external || !target || saveLock.current) return
    saveLock.current = true
    setSaving(true)
    setSaveError(null)
    setSavedFor(null)
    try {
      const saved = await trainingApi.createExternalDatasetReference({
        provider: external.providerId,
        datasetId: external.dataset.dataset_id,
        purpose: "training",
        targetType: target.type,
        targetId: target.id,
        accessMode: "reference",
        metadata: { source: "intelligence_data" },
      })
      if (!saved.id) throw new Error("The server did not confirm the import. Try again.")
      setSavedFor(target.label)
      void sources.references.mutate()
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : "Could not import this dataset.")
    } finally {
      saveLock.current = false
      setSaving(false)
    }
  }

  return (
    <section aria-labelledby="data-preview-heading" className={shell} data-review-surface="external-dataset-inspect">
      <p className={TYPE.eyebrow}>Preview</p>
      <h2 id="data-preview-heading" className="mt-1 break-all font-mono text-[15px] font-medium text-[color:var(--g-text-primary)]">
        {external!.dataset.dataset_id}
      </h2>

      {inspect.error ? (
        <div className="mt-4">
          <WorkSectionErrorCard title="Could not load dataset preview" message="Retry before importing this dataset." onRetry={() => void inspect.mutate()} />
        </div>
      ) : inspect.isLoading ? (
        <p role="status" className={cn(TYPE.bodyMuted, "mt-4")}>Reading provider metadata…</p>
      ) : (
        <>
          <KnowledgeMapping
            fields={fields}
            entityTypes={entityTypes}
            noFieldsNote={`${external!.providerLabel} doesn't report field names for this dataset, so fields are mapped after import.`}
          />

          <div className="mt-5 space-y-2">
            <p className="text-[13px] font-semibold text-[color:var(--g-text-primary)]">Checks before import</p>
            <ul className="space-y-1.5">
              <CheckRow ok={isPublic}>{isPublic ? "Public, no sign-in needed" : "Restricted. The owner must approve access first."}</CheckRow>
              {fields.length > 0 && entityTypes.length > 0 ? (
                <CheckRow ok={mappedCount > 0}>
                  {mappedCount > 0
                    ? `${mappedCount} of ${fields.length} fields match your knowledge entities`
                    : "No fields match your knowledge entities yet"}
                </CheckRow>
              ) : null}
              {details && details.materializationAllowed === false ? (
                <CheckRow ok={false}>The provider doesn&apos;t allow importing this dataset</CheckRow>
              ) : null}
              <CheckRow ok={false}>
                {license ? `License: ${license}. Review it before commercial use` : "License not reported. Review the license before commercial use"}
              </CheckRow>
            </ul>
          </div>
        </>
      )}

      <div className="mt-6 flex flex-col gap-2 border-t border-[color:var(--g-border-subtle)] pt-5 sm:flex-row">
        <Button
          variant="brand"
          className="min-h-11 flex-1"
          disabled={!target || saving || Boolean(inspect.error) || inspect.isLoading || !isPublic}
          title={!target ? "Create a model or agent first, then save data to train it." : "Saves this dataset as training data for the selected model or agent. Only metadata is read until training starts."}
          onClick={() => void importForTarget()}
        >
          {saving ? "Importing…" : target ? `Import to train ${target.label}` : "Import for training"}
        </Button>
        <Button variant="outline" className="min-h-11" disabled={saving} onClick={() => setUseForOpen(true)}>
          Use for…
        </Button>
      </div>
      {!target && !sources.mlModels.isLoading ? (
        <p className={cn(TYPE.meta, "mt-2")}>
          No models yet.{" "}
          <Link href={APP_ROUTES.intelligenceModelStudio} className="font-medium text-[color:var(--g-brand-active)] hover:underline">
            Create a model
          </Link>
        </p>
      ) : null}
      {saveError ? <p role="alert" className="mt-3 text-sm text-destructive">{saveError}</p> : null}
      {savedFor ? (
        <p role="status" className="mt-3 text-sm text-[color:var(--g-brand-active)]">
          Added to {savedFor}&apos;s training data. Gravitre has read metadata only; no files were downloaded.
        </p>
      ) : null}
      <UseForDialog
        open={useForOpen}
        onOpenChange={setUseForOpen}
        providerId={external!.providerId}
        datasetId={external!.dataset.dataset_id}
        sources={sources}
      />
    </section>
  )
}

function CheckRow({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-2 text-[13px] text-[color:var(--g-text-primary)]">
      {ok ? (
        <Check aria-label="Passed" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[color:var(--g-brand-active)]" />
      ) : (
        <AlertCircle aria-label="Check" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[color:var(--g-warning)]" />
      )}
      <span>{children}</span>
    </li>
  )
}

/** "How it maps to your knowledge": each dataset field and the knowledge entity type it matches by name. */
function KnowledgeMapping({
  fields,
  entityTypes,
  noFieldsNote,
}: {
  fields: string[]
  entityTypes: string[]
  noFieldsNote: string
}) {
  return (
    <div className="mt-5 space-y-2">
      <p className="text-[13px] font-semibold text-[color:var(--g-text-primary)]">How it maps to your knowledge</p>
      {fields.length === 0 ? (
        <p className={TYPE.meta}>{noFieldsNote}</p>
      ) : entityTypes.length === 0 ? (
        <p className={TYPE.meta}>
          No knowledge entities yet, so there&apos;s nothing to map to.{" "}
          <Link href={APP_ROUTES.learning} className="font-medium text-[color:var(--g-brand-active)] hover:underline">
            See it in Knowledge
          </Link>
        </p>
      ) : null}
      {fields.length > 0 ? (
        <ul className="space-y-2">
          {fields.map((field) => {
            const entity = mapFieldToEntity(field, entityTypes)
            return (
              <li key={field} className="grid grid-cols-[minmax(0,1fr)_20px_minmax(0,1fr)] items-center gap-2">
                <span className="truncate rounded-[7px] bg-[color:var(--g-surface-2)] px-2.5 py-1.5 font-mono text-xs text-[color:var(--g-text-primary)]">{field}</span>
                <span aria-hidden className="text-center text-xs text-[color:var(--g-text-muted)]">→</span>
                {entity ? (
                  <span className="truncate rounded-[7px] border border-[color:var(--g-intelligence)]/25 bg-[color:var(--g-intelligence-surface)] px-2.5 py-1.5 text-[13px] text-[color:var(--g-intelligence)]">
                    <span className="sr-only">maps to </span>{entityLabel(entity)}
                  </span>
                ) : (
                  <span className="truncate rounded-[7px] border border-dashed border-[color:var(--g-border-default)] px-2.5 py-1.5 text-[13px] text-[color:var(--g-text-muted)]">Not mapped</span>
                )}
              </li>
            )
          })}
        </ul>
      ) : null}
    </div>
  )
}
