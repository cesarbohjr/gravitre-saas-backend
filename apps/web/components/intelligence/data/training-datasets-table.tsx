"use client"

/**
 * "Training datasets": what each model learned from. Rows are the org's own
 * training datasets plus public datasets saved for a model or agent. "Trains"
 * comes from models that record the dataset (ml_models.dataset_id, fine-tuned
 * models' datasetId) and from the saved reference's target.
 */
import Link from "next/link"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { EXTERNAL_DATASET_PURPOSES } from "@/components/intelligence/external-datasets-section"
import { APP_ROUTES } from "@/lib/app-routes"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { ageInDays, formatShortDate } from "./format"
import type { DataSources } from "./use-data-sources"

const BUILT_FROM: Record<string, string> = {
  examples: "Examples you added",
  documents: "Documents you added",
  feedback: "Ask Gravitre feedback",
}

type Trains = { key: string; label: string; href: string; note?: string }

type Row = {
  key: string
  name: string
  detail: string
  builtFrom: string
  trains: Trains[]
  freshAt?: string | null
  onManage?: () => void
}

export function TrainingDatasetsTable({
  sources,
  onManageDataset,
}: {
  sources: DataSources
  onManageDataset: (datasetId: string) => void
}) {
  const datasets = sources.datasets.data?.datasets ?? []
  const models = sources.mlModels.data?.models ?? []
  const fineTuned = sources.fineTuned.data?.models ?? []
  const agents = sources.agents.data?.agents ?? []
  const references = sources.references.data?.references ?? []
  const providers = sources.providers.data?.providers ?? []
  const jobs = sources.jobs.data?.jobs ?? []

  const rows: Row[] = [
    ...datasets.map((dataset): Row => {
      const trains: Trains[] = [
        ...models
          .filter((m) => m.datasetId === dataset.id)
          .map((m) => ({ key: `ml:${m.id}`, label: m.name || "Untitled model", href: `${APP_ROUTES.models}/${m.id}` })),
        ...fineTuned
          .filter((m) => m.datasetId === dataset.id)
          .map((m) => ({ key: `ft:${m.id}`, label: m.name || "Fine-tuned model", href: `${APP_ROUTES.models}#fine-tunes` })),
      ]
      const activeJob = jobs.find((j) => j.dataset_id === dataset.id && (j.status === "queued" || j.status === "training"))
      if (activeJob && trains.length === 0) {
        trains.push({ key: `job:${activeJob.id}`, label: "Training run in progress", href: `${APP_ROUTES.models}#training` })
      }
      return {
        key: `own:${dataset.id}`,
        name: dataset.name,
        detail: `${dataset.record_count} record${dataset.record_count === 1 ? "" : "s"}`,
        builtFrom: BUILT_FROM[dataset.type] ?? "Your data",
        trains,
        freshAt: dataset.updated_at || dataset.created_at,
        onManage: () => onManageDataset(dataset.id),
      }
    }),
    ...references.map((ref): Row => {
      const purpose = EXTERNAL_DATASET_PURPOSES.find((p) => p.value === ref.purpose)?.label ?? ref.purpose
      const note = ref.purpose === "training" || ref.purpose === "fine_tuning" ? undefined : purpose
      let target: Trains | null = null
      if (ref.target_type === "model") {
        const model = models.find((m) => m.id === ref.target_id)
        target = { key: ref.id, label: model?.name || "A model", href: `${APP_ROUTES.models}/${ref.target_id}`, note }
      } else if (ref.target_type === "agent") {
        const agent = agents.find((a) => String(a.id) === ref.target_id)
        target = { key: ref.id, label: agent?.name || "An agent", href: `${APP_ROUTES.agents}/${ref.target_id}`, note }
      } else if (ref.target_type === "workflow") {
        target = { key: ref.id, label: "A workflow", href: `${APP_ROUTES.workflows}/${ref.target_id}`, note }
      } else if (ref.target_type === "department") {
        target = { key: ref.id, label: ref.target_id.charAt(0).toUpperCase() + ref.target_id.slice(1), href: `${APP_ROUTES.agents}`, note }
      } else if (ref.target_type === "play") {
        target = { key: ref.id, label: "A Play", href: `${APP_ROUTES.plays}`, note }
      }
      return {
        key: `ref:${ref.id}`,
        name: ref.external_dataset_id,
        detail: "metadata only",
        builtFrom: providers.find((p) => p.id === ref.provider)?.label ?? ref.provider,
        trains: target ? [target] : [],
        freshAt: ref.created_at,
      }
    }),
  ]

  const loading = (sources.datasets.isLoading || sources.references.isLoading) && rows.length === 0
  const error = sources.datasets.error && sources.references.error

  return (
    <section
      aria-labelledby="data-training-heading"
      className="overflow-hidden rounded-[var(--g-radius-card)] border border-[color:var(--g-border-subtle)] bg-card"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--g-border-subtle)] px-5 py-4">
        <h2 id="data-training-heading" className={TYPE.cardTitle}>Training datasets</h2>
        <span className={TYPE.meta}>What each model learned from</span>
      </div>
      {error ? (
        <WorkSectionErrorCard
          title="Could not load training datasets"
          message="Try again to see what each model learned from."
          onRetry={() => { void sources.datasets.mutate(); void sources.references.mutate() }}
        />
      ) : loading ? (
        <p role="status" className={cn(TYPE.bodyMuted, "px-5 py-6")}>Loading datasets…</p>
      ) : rows.length === 0 ? (
        <p className={cn(TYPE.bodyMuted, "px-5 py-6")}>
          No training datasets yet. Upload a file, save chat feedback or load starter examples above.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left">
            <thead>
              <tr className="border-b border-[color:var(--g-border-subtle)]">
                <th scope="col" className={cn(TYPE.tableHead, "px-5 py-3")}>Dataset</th>
                <th scope="col" className={cn(TYPE.tableHead, "px-5 py-3")}>Built from</th>
                <th scope="col" className={cn(TYPE.tableHead, "px-5 py-3")}>Trains</th>
                <th scope="col" className={cn(TYPE.tableHead, "px-5 py-3")}>Freshness</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[color:var(--g-border-subtle)]">
              {rows.map((row) => {
                const age = ageInDays(row.freshAt)
                return (
                  <tr key={row.key} className="hover:bg-[color:var(--g-surface-2)]/60">
                    <td className="px-5 py-3 align-top">
                      {row.onManage ? (
                        <button
                          type="button"
                          onClick={row.onManage}
                          className="text-left font-mono text-[13px] text-[color:var(--g-text-primary)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--g-brand)]"
                          title="Edit this dataset"
                        >
                          {row.name}
                        </button>
                      ) : (
                        <span className="break-all font-mono text-[13px] text-[color:var(--g-text-primary)]">{row.name}</span>
                      )}
                      <span className="font-mono text-[13px] text-[color:var(--g-text-muted)]"> · {row.detail}</span>
                    </td>
                    <td className="px-5 py-3 align-top text-[13px] text-[color:var(--g-text-primary)]">{row.builtFrom}</td>
                    <td className="px-5 py-3 align-top text-[13px]">
                      {row.trains.length === 0 ? (
                        <span className="text-[color:var(--g-text-muted)]">Not used yet</span>
                      ) : (
                        <span className="flex flex-col gap-1">
                          {row.trains.map((t) => (
                            <span key={t.key}>
                              <Link href={t.href} className="text-[color:var(--g-brand-active)] underline underline-offset-2 hover:text-[color:var(--g-brand-hover)]">
                                {t.label}
                              </Link>
                              {t.note ? <span className="text-[color:var(--g-text-muted)]"> · {t.note.toLowerCase()}</span> : null}
                            </span>
                          ))}
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3 align-top">
                      <span
                        className={cn(
                          "inline-flex rounded-[4px] px-1.5 py-0.5 text-xs",
                          age == null
                            ? "text-[color:var(--g-text-muted)]"
                            : age > 30
                              ? "bg-[color:var(--g-approval-surface)] text-[color:var(--g-approval)]"
                              : "bg-[color:var(--g-surface-2)] text-[color:var(--g-text-secondary)]",
                        )}
                        title={age == null ? "Not reported" : age > 30 ? `Last updated ${age} days ago` : undefined}
                      >
                        {formatShortDate(row.freshAt)}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
