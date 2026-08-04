import { useState } from "react"
import { GitBranch } from "lucide-react"

import { Button, SectionLabel } from "@/components/ui"
import { cn } from "@/lib/cn"
import type { ExtensionWorkflow } from "@/lib/types"

/**
 * Multi-step workflow plan bar (Part D).
 *
 * The main app's chat surfaces a plan as an ordered list of steps you approve as
 * a unit; this mirrors that so the same mental model carries over. Numbered
 * markers are used here deliberately — unlike decorative "01/02/03" labels,
 * these steps really do execute in sequence.
 */
export function WorkflowSection({
  workflows,
  loading,
  error,
  busyId,
  onRun,
}: {
  workflows: ExtensionWorkflow[]
  loading: boolean
  error?: string
  busyId?: string
  onRun: (workflow: ExtensionWorkflow) => void
}) {
  const [openId, setOpenId] = useState<string | null>(null)

  // Render nothing at all rather than an empty shell: an org with no workflows
  // should not see a section implying it is missing something (D.3).
  if (!loading && !error && !workflows.length) return null

  return (
    <div>
      <SectionLabel>Workflows</SectionLabel>

      {loading && (
        <p className="mt-1.5 text-[12px] text-muted-foreground">Loading workflows…</p>
      )}
      {error && <p className="mt-1.5 text-[12px] text-muted-foreground">{error}</p>}

      {!loading && !error && (
        <ul className="mt-1.5 flex flex-col gap-1.5">
          {workflows.slice(0, 5).map((wf) => {
            const open = openId === wf.id
            const steps = wf.progressSteps || []
            return (
              <li
                key={wf.id}
                className="overflow-hidden rounded-lg border border-border bg-card"
              >
                <button
                  type="button"
                  onClick={() => setOpenId(open ? null : wf.id)}
                  aria-expanded={open}
                  className={cn(
                    "flex w-full items-center gap-2 px-2.5 py-2 text-left",
                    "outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    "hover:bg-secondary/60",
                  )}
                >
                  <GitBranch
                    aria-hidden="true"
                    className="h-3.5 w-3.5 shrink-0 text-muted-foreground"
                  />
                  <span className="min-w-0 flex-1 truncate text-[12px] font-medium text-foreground">
                    {wf.name}
                  </span>
                  <span className="shrink-0 text-[11px] text-muted-foreground">
                    {wf.stepCount} {wf.stepCount === 1 ? "step" : "steps"}
                  </span>
                </button>

                {open && (
                  <div className="gvt-animate-row border-t border-border px-2.5 py-2.5">
                    {steps.length > 0 && (
                      <ol className="flex flex-col gap-1.5">
                        {steps.map((step, i) => (
                          <li key={`${step.name}-${i}`} className="flex items-start gap-2">
                            <span
                              aria-hidden="true"
                              className={cn(
                                "mt-px flex h-4 w-4 shrink-0 items-center justify-center rounded-full",
                                "bg-secondary text-[10px] font-semibold text-muted-foreground",
                              )}
                            >
                              {i + 1}
                            </span>
                            <div className="min-w-0 flex-1">
                              <p className="text-[12px] leading-snug text-foreground">
                                {step.name}
                              </p>
                              {step.action && (
                                <p className="truncate font-mono text-[10px] text-muted-foreground">
                                  {step.action}
                                </p>
                              )}
                            </div>
                          </li>
                        ))}
                      </ol>
                    )}

                    <p className="mt-2.5 text-[11px] leading-relaxed text-muted-foreground">
                      Approving runs every step above. Each write is recorded in Outcomes.
                    </p>

                    <div className="mt-2.5 flex items-center gap-2">
                      <Button
                        variant="primary"
                        size="sm"
                        loading={busyId === wf.id}
                        onClick={() => onRun(wf)}
                        className="flex-1"
                      >
                        {busyId === wf.id ? "Running…" : "Approve & run workflow"}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setOpenId(null)}
                        disabled={busyId === wf.id}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
