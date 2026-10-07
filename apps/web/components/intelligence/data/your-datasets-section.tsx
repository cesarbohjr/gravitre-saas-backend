"use client"

/** "Your datasets": the three ways to add the org's own training material. */
import { useRef, useState, type ReactNode } from "react"
import { MessageSquare, Sparkles, Upload } from "lucide-react"
import { toast } from "sonner"
import { trainingApi } from "@/lib/api"
import { TYPE } from "@/lib/design-system"
import { ensureSelectedOrg } from "@/lib/org-context"
import { cn } from "@/lib/utils"
import { STARTER_DATASET, STARTER_EXAMPLES } from "@/components/training/starter-examples"
import type { TrainingDataset } from "@/types/api"

export function YourDatasetsSection({
  datasets,
  datasetsReady,
  onUpload,
  onChanged,
}: {
  datasets: TrainingDataset[]
  datasetsReady: boolean
  onUpload: () => void
  onChanged: () => void
}) {
  const lock = useRef(false)
  const [pending, setPending] = useState<"feedback" | "starter" | null>(null)
  // A starter dataset created before a failed record upload is retried, not duplicated.
  const [starterId, setStarterId] = useState<string | null>(null)

  async function run(kind: "feedback" | "starter", work: () => Promise<void>) {
    if (lock.current) return
    lock.current = true
    setPending(kind)
    try {
      if (!(await ensureSelectedOrg(true))) throw new Error("Workspace membership is required.")
      await work()
    } catch (error) {
      toast.error(kind === "feedback" ? "Could not save chat feedback" : "Could not load starter examples", {
        description: error instanceof Error ? error.message : "Try again.",
      })
    } finally {
      onChanged()
      lock.current = false
      setPending(null)
    }
  }

  const saveFeedback = () =>
    run("feedback", async () => {
      const existing = datasets.find((d) => d.type === "feedback")
      const id =
        existing?.id ??
        (await trainingApi.createDataset({
          name: "Ask Gravitre feedback",
          type: "feedback",
          description: "Thumbs up, thumbs down and corrections from Ask Gravitre.",
        })).id
      const result = await trainingApi.importFeedback(id, 50)
      if (result.added === 0) {
        toast.message("No new chat feedback yet", {
          description: "Rate answers in Ask Gravitre as helpful or not, then try again.",
        })
      } else {
        toast.success(`Saved ${result.added} feedback example${result.added === 1 ? "" : "s"} to ${existing?.name ?? "Ask Gravitre feedback"}`)
      }
    })

  const loadStarter = () =>
    run("starter", async () => {
      const id = starterId ?? (await trainingApi.createDataset({ ...STARTER_DATASET })).id
      setStarterId(id)
      const result = await trainingApi.uploadRecords(id, [...STARTER_EXAMPLES])
      setStarterId(null)
      toast.success(`Loaded ${result.added} starter example${result.added === 1 ? "" : "s"}`)
    })

  return (
    <section aria-labelledby="data-yours-heading" id="yours" className="scroll-mt-24 space-y-3">
      <div>
        <h2 id="data-yours-heading" className={TYPE.sectionTitle}>Your datasets</h2>
        <p className={cn(TYPE.bodyMuted, "mt-1")}>
          Examples, documents and chat feedback you add. Use them to train models and coach agents.
        </p>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        <ActionCard
          icon={<Upload aria-hidden className="h-5 w-5" />}
          title="Upload a file"
          body="CSV, JSON or documents. Gravitre checks every row as it reads."
          onClick={onUpload}
          disabled={!datasetsReady}
        />
        <ActionCard
          icon={<MessageSquare aria-hidden className="h-5 w-5" />}
          title={pending === "feedback" ? "Saving chat feedback…" : "Save chat feedback"}
          body="Turn thumbs up and corrections from Ask Gravitre into training examples."
          onClick={() => void saveFeedback()}
          disabled={!datasetsReady || pending !== null}
        />
        <ActionCard
          tone="brand"
          icon={<Sparkles aria-hidden className="h-5 w-5" />}
          title={pending === "starter" ? "Loading starter examples…" : starterId ? "Retry starter examples" : "Load starter examples"}
          body="A small labelled set of example requests and answers. Ready in a few seconds."
          onClick={() => void loadStarter()}
          disabled={!datasetsReady || pending !== null}
        />
      </div>
    </section>
  )
}

function ActionCard({
  icon,
  title,
  body,
  onClick,
  disabled,
  tone = "neutral",
}: {
  icon: ReactNode
  title: string
  body: string
  onClick: () => void
  disabled?: boolean
  tone?: "neutral" | "brand"
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "flex min-h-11 flex-col items-start gap-2.5 rounded-[var(--g-radius-card)] border-[1.5px] p-5 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--g-brand)]",
        tone === "brand"
          ? "border-solid border-[color:var(--g-brand)]/25 bg-[color:var(--g-brand-surface)] hover:border-[color:var(--g-brand)]/60"
          : "border-dashed border-[color:var(--g-border-default)] bg-card hover:border-[color:var(--g-border-strong)]",
      )}
    >
      <span
        className={cn(
          "grid h-10 w-10 place-items-center rounded-[var(--g-radius-control)]",
          tone === "brand"
            ? "bg-[color:var(--g-brand)]/15 text-[color:var(--g-brand-active)]"
            : "bg-[color:var(--g-surface-2)] text-[color:var(--g-text-secondary)]",
        )}
      >
        {icon}
      </span>
      <span className="space-y-1.5">
        <span className={cn(TYPE.cardTitle, "block")}>{title}</span>
        <span className={cn(TYPE.meta, "block text-[13px] leading-relaxed", tone === "brand" && "text-[color:var(--g-text-secondary)]")}>{body}</span>
      </span>
    </button>
  )
}
