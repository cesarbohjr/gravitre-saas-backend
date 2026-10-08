"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import useSWR from "swr"
import { toast } from "sonner"
import { ArrowLeft, ArrowRight, Loader2, RefreshCw } from "lucide-react"
import { apiFetch } from "@/lib/fetcher"
import { connectorsApi, workflowsApi } from "@/lib/api"
import { CONNECTOR_CATALOG } from "@/lib/connectors"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"

type Plan = {
  goalSummary: string
  steps: { id: string; name: string; description: string; type: "task" }[]
  requiredConnectors: { id: string; name: string; connected: boolean | null }[]
  approvalGates: { stepId: string; reason: string; required: boolean | null }[]
  estimatedRuntime: string | null
  riskLevel: string | null
  successMetric: string
}
const CATEGORIES = [
  "marketing",
  "sales",
  "support",
  "finance",
  "reporting",
  "operations",
]
const selectClass =
  "min-h-11 w-full rounded-md border border-input bg-background px-3 text-sm"

export function GoalWorkflowWizard({
  open,
  onOpenChange,
  onBuildWorkflow,
  onGoalSaved,
  initial,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onBuildWorkflow?: (plan: Plan) => void
  onGoalSaved?: () => void
  /** Prefill for a suggested goal (e.g. from the Agents work map). */
  initial?: {
    objective?: string
    category?: string
    department?: string
    metric?: string
    systems?: string[]
  }
}) {
  const router = useRouter()
  const [step, setStep] = useState(1)
  const [objective, setObjective] = useState("")
  const [category, setCategory] = useState("")
  const [department, setDepartment] = useState("")
  const [priority, setPriority] = useState("medium")
  const [frequency, setFrequency] = useState("once")
  const [metric, setMetric] = useState("")
  const [systems, setSystems] = useState<string[]>([])
  const [plan, setPlan] = useState<Plan | null>(null)
  const [busy, setBusy] = useState<"save" | "plan" | "build" | null>(null)
  const [planId, setPlanId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [goalId, setGoalId] = useState<string | null>(null)
  const persistedId = useRef<string | null>(null)
  const lock = useRef(false)
  const wasOpen = useRef(false)
  const {
    data,
    error: connectorError,
    isLoading: connectorLoading,
    mutate,
  } = useSWR(open ? "goals/create/connectors" : null, () =>
    connectorsApi.list(),
  )
  const connections = data?.connectors ?? []
  const connectionState = (vendor: string): boolean | null => {
    if (!data || connectorError) return null
    return connections.some(
      (c) =>
        [c.vendor, c.type, c.id].some(
          (v) => v?.toLowerCase() === vendor.toLowerCase(),
        ) && c.status === "active",
    )
  }
  useEffect(() => {
    if (open && !wasOpen.current) {
      setStep(1)
      setObjective(initial?.objective ?? "")
      setCategory(
        initial?.category && CATEGORIES.includes(initial.category)
          ? initial.category
          : "",
      )
      setDepartment(initial?.department ?? "")
      setPriority("medium")
      setFrequency("once")
      setMetric(initial?.metric ?? "")
      setSystems(initial?.systems ?? [])
      setPlan(null)
      setPlanId(null)
      setError(null)
      setGoalId(null)
      persistedId.current = null
    }
    wasOpen.current = open
    // eslint-disable-next-line react-hooks/exhaustive-deps -- prefill applies once per open
  }, [open])
  function close(next: boolean) {
    if (!lock.current) onOpenChange(next)
  }
  async function persist() {
    const id = persistedId.current
    const response = await apiFetch(id ? `/api/goals/${id}` : "/api/goals", {
      method: id ? "PATCH" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        objective: objective.trim(),
        category: category || null,
        priority,
        frequency,
        department: department.trim() || null,
        connectedSystems: systems,
        successMetrics: metric.trim() ? { primary: metric.trim() } : {},
        status: "draft",
      }),
    })
    if (!response.ok)
      throw new Error(
        "Could not save this goal. Your edits are retained; try again.",
      )
    const result = (await response.json()) as { goal?: { id?: string } }
    const saved = result.goal?.id || id
    if (!saved)
      throw new Error(
        "The server did not return a saved goal. Check the goal list before trying again.",
      )
    persistedId.current = saved
    setGoalId(saved)
    onGoalSaved?.()
    return saved
  }
  async function run(kind: "save" | "plan") {
    if (lock.current || !objective.trim()) return
    lock.current = true
    setBusy(kind)
    setError(null)
    try {
      const id = await persist()
      if (kind === "save") {
        toast.success("Goal saved as draft")
        lock.current = false
        close(false)
        return
      }
      const response = await apiFetch(`/api/goals/${id}/generate-plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          objective: objective.trim(),
          context: [
            department.trim() ? `Department: ${department.trim()}` : "",
            systems.length ? `Requested systems: ${systems.join(", ")}` : "",
            metric.trim() ? `Success metric: ${metric.trim()}` : "",
          ]
            .filter(Boolean)
            .join("\n"),
          constraints: metric.trim() ? [metric.trim()] : [],
        }),
      })
      if (!response.ok)
        throw new Error(
          "Your goal is saved as a draft. Plan generation failed; your context is retained for retry.",
        )
      const payload = (await response.json()) as Record<string, unknown>
      const savedPlanId =
        typeof payload.planId === "string"
          ? payload.planId
          : typeof (payload.goalPlan as { id?: string } | undefined)?.id ===
              "string"
            ? (payload.goalPlan as { id: string }).id
            : null
      if (!savedPlanId) {
        throw new Error(
          "The planner responded but did not persist a proposal. Your goal remains saved; try generating again.",
        )
      }
      setPlanId(savedPlanId)
      const source = (payload.goalPlan ?? payload) as Record<string, unknown>
      const steps = Array.isArray(source.proposedSteps)
        ? (source.proposedSteps as Record<string, unknown>[])
        : []
      const connectors = Array.isArray(source.requiredConnectors)
        ? source.requiredConnectors.filter(
            (v): v is string => typeof v === "string",
          )
        : []
      const gates = Array.isArray(source.approvalGates)
        ? (source.approvalGates as Record<string, unknown>[])
        : []
      setPlan({
        goalSummary: objective.trim(),
        steps: steps.map((s, i) => ({
          id: String(s.id ?? i),
          name: String(s.title ?? s.name ?? "Unnamed proposed step"),
          description: String(s.description ?? s.title ?? s.name ?? ""),
          type: "task",
        })),
        requiredConnectors: connectors.map((id) => ({
          id,
          name: id.replace(/_/g, " "),
          connected: connectionState(id),
        })),
        approvalGates: gates.map((g, i) => ({
          stepId: String(g.stepId ?? i),
          reason: String(g.reason ?? g.phase ?? "Approval policy"),
          required: typeof g.required === "boolean" ? g.required : null,
        })),
        estimatedRuntime:
          typeof source.estimatedRuntime === "string"
            ? source.estimatedRuntime
            : null,
        riskLevel:
          typeof source.riskLevel === "string" ? source.riskLevel : null,
        successMetric: metric.trim(),
      })
      setStep(3)
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Could not complete this request. Try again.",
      )
    } finally {
      lock.current = false
      setBusy(null)
    }
  }
  async function openBuilder() {
    if (lock.current || !plan || !goalId) return
    lock.current = true
    setBusy("build")
    setError(null)
    try {
      const result = await workflowsApi.fromGoal({
        goal: objective.trim(),
        department: department.trim() || undefined,
        connectors: systems.length ? systems : undefined,
        successMetric: metric.trim() || undefined,
        approvalRequired: plan.approvalGates.some((gate) => gate.required === true),
        orgContext: [
          department.trim() ? `Department: ${department.trim()}` : "",
          systems.length ? `Requested systems: ${systems.join(", ")}` : "",
          metric.trim() ? `Success metric: ${metric.trim()}` : "",
          planId ? `Persisted proposal: ${planId}` : "",
        ]
          .filter(Boolean)
          .join("\n"),
        goalId,
      })
      if (!result.id) {
        throw new Error(
          "The goal and proposal are saved, but the server did not return a workflow. Try opening the builder again.",
        )
      }
      onBuildWorkflow?.(plan)
      close(false)
      router.push(`/workflows/${result.id}/builder`)
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Could not create a workflow from this proposal. The saved goal and plan remain.",
      )
    } finally {
      lock.current = false
      setBusy(null)
    }
  }
  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent
        className="flex max-h-[90dvh] max-w-3xl flex-col overflow-hidden"
        data-composition="create"
      >
        <DialogHeader>
          <p className={TYPE.eyebrow}>Create / Business objective</p>
          <DialogTitle className="font-sans">
            Start with the outcome
          </DialogTitle>
          <DialogDescription>
            Define success, choose context and review a proposed plan before
            building or executing work.
          </DialogDescription>
        </DialogHeader>
        <ol
          aria-label="Goal creation steps"
          className="flex gap-4 border-b border-border pb-3 text-sm"
        >
          {["Objective", "Context", "Review"].map((label, i) => (
            <li
              key={label}
              aria-current={step === i + 1 ? "step" : undefined}
              className={cn(
                step === i + 1
                  ? "font-medium text-[color:var(--g-brand-active)]"
                  : "text-muted-foreground",
              )}
            >
              {i + 1}. {label}
            </li>
          ))}
        </ol>
        <div className="min-h-0 overflow-y-auto space-y-5 pr-1">
          <fieldset
            disabled={busy !== null}
            className="min-w-0 space-y-5 [&_[data-slot=button]]:min-h-11 [&_input]:min-h-11"
          >
            {step === 1 ? (
              <>
                <div className="space-y-2">
                  <label htmlFor="goal-objective" className={TYPE.body}>
                    What outcome do you want?
                  </label>
                  <Textarea
                    id="goal-objective"
                    rows={4}
                    value={objective}
                    onChange={(e) => setObjective(e.target.value)}
                    placeholder="Reduce overdue invoices and define how we’ll measure the change"
                  />
                </div>
                <div className="space-y-2">
                  <label htmlFor="goal-category" className={TYPE.meta}>
                    Category
                  </label>
                  <select
                    id="goal-category"
                    className={selectClass}
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                  >
                    <option value="">Choose a category (optional)</option>
                    {CATEGORIES.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <label htmlFor="goal-priority">Priority</label>
                    <select
                      id="goal-priority"
                      className={selectClass}
                      value={priority}
                      onChange={(e) => setPriority(e.target.value)}
                    >
                      {["low", "medium", "high"].map((v) => (
                        <option key={v}>{v}</option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-2">
                    <label htmlFor="goal-frequency">Cadence</label>
                    <select
                      id="goal-frequency"
                      className={selectClass}
                      value={frequency}
                      onChange={(e) => setFrequency(e.target.value)}
                    >
                      {["once", "daily", "weekly", "monthly"].map((v) => (
                        <option key={v}>{v}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </>
            ) : null}
            {step === 2 ? (
              <>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <label htmlFor="goal-department">
                      Department (optional)
                    </label>
                    <Input
                      id="goal-department"
                      value={department}
                      onChange={(e) => setDepartment(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <label htmlFor="goal-metric">
                      Success measure (optional)
                    </label>
                    <Input
                      id="goal-metric"
                      value={metric}
                      onChange={(e) => setMetric(e.target.value)}
                      placeholder="For example: reduce overdue balance by 10%"
                    />
                  </div>
                </div>
                <section className="space-y-3">
                  <h3 className={TYPE.sectionTitle}>
                    Systems the plan may use
                  </h3>
                  <p className={TYPE.bodyMuted}>
                    These selections describe planning context. They do not
                    connect an app or grant tool permissions.
                  </p>
                  {connectorLoading ? (
                    <p role="status">Loading workspace connections…</p>
                  ) : null}
                  {connectorError ? (
                    <div role="alert">
                      <p>
                        Connection status is unavailable. You can still describe
                        the requested systems.
                      </p>
                      <Button variant="outline" onClick={() => void mutate()}>
                        Retry connections
                      </Button>
                    </div>
                  ) : null}
                  <div className="grid gap-x-4 sm:grid-cols-2">
                    {CONNECTOR_CATALOG.map((c) => (
                      <label
                        key={c.vendorKey}
                        className="flex min-h-11 items-center gap-3 border-b border-border py-2 text-sm"
                      >
                        <input
                          type="checkbox"
                          className="size-4 accent-[color:var(--g-brand)]"
                          checked={systems.includes(c.vendorKey)}
                          onChange={(e) =>
                            setSystems((prev) =>
                              e.target.checked
                                ? [...prev, c.vendorKey]
                                : prev.filter((id) => id !== c.vendorKey),
                            )
                          }
                        />
                        <span className="min-w-0 flex-1">{c.type}</span>
                        <span className={TYPE.meta}>
                          {connectionState(c.vendorKey) === null
                            ? "Not reported"
                            : connectionState(c.vendorKey)
                              ? "Connected"
                              : "Not connected"}
                        </span>
                      </label>
                    ))}
                  </div>
                </section>
              </>
            ) : null}
            {step === 3 && plan ? (
              <>
                <div className="border-l-2 border-[color:var(--g-brand)] pl-4">
                  <p className={TYPE.eyebrow}>Proposed plan</p>
                  <h3 className={cn(TYPE.sectionTitle, "mt-1")}>
                    {plan.goalSummary}
                  </h3>
                  <p className={cn(TYPE.bodyMuted, "mt-2")}>
                    The goal and this proposal are saved. Opening the builder
                    creates a real draft workflow from this objective. It does
                    not start execution.
                  </p>
                </div>
                <dl className="grid grid-cols-2 gap-4 border-y border-border py-3 text-sm">
                  <div>
                    <dt className={TYPE.meta}>Estimated runtime</dt>
                    <dd>{plan.estimatedRuntime ?? "Not reported"}</dd>
                  </div>
                  <div>
                    <dt className={TYPE.meta}>Reported risk</dt>
                    <dd>{plan.riskLevel ?? "Not reported"}</dd>
                  </div>
                </dl>
                {plan.steps.length ? (
                  <ol className="divide-y divide-border">
                    {plan.steps.map((s, i) => (
                      <li key={s.id} className="flex gap-3 py-3">
                        <span className={TYPE.eyebrow}>
                          {String(i + 1).padStart(2, "0")}
                        </span>
                        <div>
                          <p className="text-sm font-medium">{s.name}</p>
                          {s.description !== s.name ? (
                            <p className={TYPE.bodyMuted}>{s.description}</p>
                          ) : null}
                        </div>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p>Proposed steps not reported.</p>
                )}
                <section className="space-y-2">
                  <h4 className={TYPE.eyebrow}>Required systems</h4>
                  {plan.requiredConnectors.length ? (
                    plan.requiredConnectors.map((c) => (
                      <p key={c.id} className="text-sm">
                        {c.name} ·{" "}
                        {c.connected === null
                          ? "Connection not reported"
                          : c.connected
                            ? "Connected"
                            : "Not connected"}
                      </p>
                    ))
                  ) : (
                    <p className={TYPE.bodyMuted}>
                      No required systems returned.
                    </p>
                  )}
                </section>
                <section className="space-y-2">
                  <h4 className={TYPE.eyebrow}>Approval policy</h4>
                  {plan.approvalGates.length ? (
                    plan.approvalGates.map((g) => (
                      <p key={g.stepId} className="text-sm">
                        {g.reason} ·{" "}
                        {g.required === null
                          ? "Requirement not reported"
                          : g.required
                            ? "Required"
                            : "Not required by this proposal"}
                      </p>
                    ))
                  ) : (
                    <p className={TYPE.bodyMuted}>
                      Approval requirements not reported.
                    </p>
                  )}
                </section>
              </>
            ) : null}
          </fieldset>
          {busy ? (
            <p role="status" className="flex items-center gap-2 text-sm">
              <Loader2 className="size-4 animate-spin motion-reduce:animate-none" />
              {busy === "plan"
                ? "Waiting for the planner’s response…"
                : busy === "build"
                  ? "Creating the workflow…"
                  : "Saving goal…"}
            </p>
          ) : null}
          {error ? (
            <p
              role="alert"
              className="border-l-2 border-destructive pl-3 text-sm text-destructive"
            >
              {error}
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-4 [&_[data-slot=button]]:min-h-11 [&_a]:min-h-11">
          <div>
            {step > 1 ? (
              <Button
                variant="ghost"
                disabled={busy !== null}
                onClick={() => setStep(step - 1)}
              >
                <ArrowLeft className="mr-1 size-4" />
                Back
              </Button>
            ) : (
              <Button
                variant="ghost"
                disabled={busy !== null}
                onClick={() => close(false)}
              >
                Cancel
              </Button>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              disabled={busy !== null || !objective.trim()}
              onClick={() => void run("save")}
            >
              Save draft
            </Button>
            {step === 1 ? (
              <Button
                disabled={!objective.trim() || busy !== null}
                onClick={() => setStep(2)}
              >
                Continue
                <ArrowRight className="ml-1 size-4" />
              </Button>
            ) : step === 2 ? (
              <Button disabled={busy !== null} onClick={() => void run("plan")}>
                Generate plan
              </Button>
            ) : (
              <>
                <Button
                  variant="outline"
                  disabled={busy !== null}
                  onClick={() => void run("plan")}
                >
                  <RefreshCw className="mr-1 size-4" />
                  Regenerate
                </Button>
                {plan && goalId ? (
                  <Button
                    disabled={busy !== null}
                    onClick={() => void openBuilder()}
                  >
                    Open workflow builder
                  </Button>
                ) : null}
                {goalId ? (
                  <Button asChild variant={plan ? "outline" : "default"}>
                    <Link
                      href={`/goals/${goalId}`}
                      aria-disabled={busy !== null}
                      tabIndex={busy !== null ? -1 : undefined}
                      onClick={(event) => {
                        if (lock.current) event.preventDefault()
                        else close(false)
                      }}
                    >
                      Open saved goal
                    </Link>
                  </Button>
                ) : null}
              </>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
