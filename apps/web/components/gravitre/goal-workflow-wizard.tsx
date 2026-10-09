"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import useSWR from "swr"
import { toast } from "sonner"
import { ArrowLeft, ArrowRight, Loader2, Lock, RefreshCw, Sparkles, X } from "lucide-react"
import { apiFetch } from "@/lib/fetcher"
import { agentsApi, connectorsApi, workflowsApi } from "@/lib/api"
import { CONNECTOR_CATALOG } from "@/lib/connectors"
import { useAuth } from "@/lib/auth-context"
import type { GoalRecord } from "@/lib/goals-list"
import {
  GOAL_CADENCES,
  GOAL_DEPARTMENTS,
  GOAL_PRIORITIES,
  type GoalDepartmentId,
  type GoalTemplate,
  capitalize,
  departmentId,
  goalMetrics,
  goalStrengthChecks,
} from "@/lib/goal-insights"
import { cn } from "@/lib/utils"
import { DepartmentGlyph, DepartmentIcon } from "@/components/agents/department-icon"
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import "@/components/workspace/workspace.css"
import "@/components/goals/new-goal.css"

type Plan = {
  goalSummary: string
  steps: {
    id: string
    name: string
    description: string
    type: "task"
    status: string | null
    owner: string | null
  }[]
  requiredConnectors: { id: string; name: string; connected: boolean | null }[]
  requiredAgents: number | null
  approvalGates: { stepId: string; reason: string; required: boolean | null }[]
  estimatedRuntime: string | null
  riskLevel: string | null
  successMetric: string
}

const EXAMPLES = [
  "Book 20 qualified demos this quarter",
  "Reduce overdue invoices by 30% by Dec 31",
  "Get 100 MSP leads into HubSpot by Dec 31",
]

const PAUSE_OPTIONS = [
  { id: "email", label: "Sending email" },
  { id: "credits", label: "Spending credits" },
] as const

const VISIBLE_APPS = 6

function parseNumber(value: string): number | null | "invalid" {
  const trimmed = value.trim()
  if (!trimmed) return null
  const parsed = Number(trimmed.replace(/,/g, ""))
  return Number.isFinite(parsed) ? parsed : "invalid"
}

function userDisplayName(user: unknown): { id: string | null; name: string | null } {
  const u = (user ?? {}) as {
    id?: string
    email?: string
    user_metadata?: { full_name?: string; name?: string }
  }
  const name =
    u.user_metadata?.full_name?.trim() ||
    u.user_metadata?.name?.trim() ||
    (u.email ? u.email.split("@")[0] : "") ||
    null
  return { id: u.id ?? null, name }
}

/** What a template or suggestion can prefill. GoalTemplate fits this shape. */
export type GoalPrefill = Pick<GoalTemplate, "objective"> & {
  department?: GoalDepartmentId | null
  metric?: string
  systems?: string[]
}

export function GoalWorkflowWizard({
  open,
  onOpenChange,
  onBuildWorkflow,
  onGoalSaved,
  initialGoal = null,
  template = null,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onBuildWorkflow?: (plan: Plan) => void
  onGoalSaved?: () => void
  /** Continue setting up a saved goal instead of starting a new one. */
  initialGoal?: GoalRecord | null
  /** Prefill a new goal from a goal template or a suggestion (text only, never numbers). */
  template?: GoalPrefill | null
}) {
  const router = useRouter()
  const { user } = useAuth()
  const [step, setStep] = useState(1)
  const [objective, setObjective] = useState("")
  const [department, setDepartment] = useState<GoalDepartmentId | "">("")
  const [priority, setPriority] = useState("medium")
  const [frequency, setFrequency] = useState("once")
  const [metric, setMetric] = useState("")
  const [start, setStart] = useState("")
  const [target, setTarget] = useState("")
  const [dueDate, setDueDate] = useState("")
  const [systems, setSystems] = useState<string[]>([])
  const [pauseBefore, setPauseBefore] = useState<string[]>(["email"])
  const [notes, setNotes] = useState("")
  const [showAllApps, setShowAllApps] = useState(false)
  const [plan, setPlan] = useState<Plan | null>(null)
  const [busy, setBusy] = useState<"save" | "plan" | "build" | "approve" | null>(null)
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
  const { data: agentData } = useSWR(
    open && step === 2 && department ? "goals/create/agents" : null,
    () => agentsApi.list(),
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
      const g = initialGoal
      const m = g ? goalMetrics(g) : null
      const sm = (g?.successMetrics ?? {}) as Record<string, unknown>
      setStep(1)
      setObjective(g?.objective ?? template?.objective ?? "")
      setDepartment(departmentId(g?.department) ?? template?.department ?? "")
      setPriority(g?.priority?.toLowerCase() || "medium")
      setFrequency(g?.frequency?.toLowerCase() || "once")
      setMetric(m?.metric ?? template?.metric ?? "")
      setStart(m?.start !== null && m?.start !== undefined ? String(m.start) : "")
      setTarget(m?.target !== null && m?.target !== undefined ? String(m.target) : "")
      setDueDate(m?.dueDate ?? "")
      setSystems(g?.connectedSystems ?? template?.systems ?? [])
      setPauseBefore(
        Array.isArray(sm.pauseBefore)
          ? (sm.pauseBefore as unknown[]).filter((v): v is string => typeof v === "string")
          : ["email"],
      )
      setNotes(typeof sm.context === "string" ? sm.context : "")
      setShowAllApps(false)
      setPlan(null)
      setPlanId(null)
      setError(null)
      setGoalId(g?.id ?? null)
      persistedId.current = g?.id ?? null
    }
    wasOpen.current = open
  }, [open, initialGoal, template])

  const deptLabel = GOAL_DEPARTMENTS.find((d) => d.id === department)?.label ?? ""
  const checks = goalStrengthChecks({ objective, target, dueDate })
  const metricLine = [
    metric.trim(),
    target.trim() ? `target ${target.trim()}` : "",
    start.trim() ? `from ${start.trim()}` : "",
    dueDate ? `due ${dueDate}` : "",
  ]
    .filter(Boolean)
    .join(", ")
  const pauseLines = [
    "Pause before writing to the CRM",
    ...PAUSE_OPTIONS.filter((p) => pauseBefore.includes(p.id)).map(
      (p) => `Pause before ${p.label.toLowerCase()}`,
    ),
  ]

  function close(next: boolean) {
    if (!lock.current) onOpenChange(next)
  }
  async function persist() {
    const id = persistedId.current
    const startValue = parseNumber(start)
    const targetValue = parseNumber(target)
    if (startValue === "invalid" || targetValue === "invalid") {
      throw new Error("Use a plain number for the start and target values.")
    }
    const existing = (initialGoal?.successMetrics ?? {}) as Record<string, unknown>
    const owner =
      existing.owner && typeof existing.owner === "object"
        ? existing.owner
        : (() => {
            const who = userDisplayName(user)
            return who.name ? who : undefined
          })()
    const successMetrics: Record<string, unknown> = {
      ...existing,
      metric: metric.trim() || null,
      start: startValue,
      target: targetValue,
      dueDate: dueDate || null,
      pauseBefore,
      context: notes.trim() || null,
    }
    if (owner) successMetrics.owner = owner
    if (metric.trim()) successMetrics.primary = metric.trim()
    else delete successMetrics.primary
    const response = await apiFetch(id ? `/api/goals/${id}` : "/api/goals", {
      method: id ? "PATCH" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        objective: objective.trim(),
        category: department || null,
        priority,
        frequency,
        department: deptLabel || null,
        connectedSystems: systems,
        successMetrics,
        ...(id ? {} : { status: "draft" }),
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
            deptLabel ? `Department: ${deptLabel}` : "",
            systems.length ? `Requested systems: ${systems.join(", ")}` : "",
            metricLine ? `Success metric: ${metricLine}` : "",
            `Approval: ${pauseLines.join("; ")}`,
            notes.trim() ? `Notes: ${notes.trim()}` : "",
          ]
            .filter(Boolean)
            .join("\n"),
          constraints: [...(metricLine ? [metricLine] : []), ...pauseLines],
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
      const agents = Array.isArray(source.requiredAgents)
        ? source.requiredAgents.length
        : 0
      setPlan({
        goalSummary: objective.trim(),
        steps: steps.map((s, i) => ({
          id: String(s.id ?? i),
          name: String(s.title ?? s.name ?? "Unnamed proposed step"),
          description: String(s.why ?? s.description ?? s.title ?? s.name ?? ""),
          type: "task",
          status: typeof s.status === "string" ? s.status : null,
          owner: typeof s.owner === "string" && s.owner ? s.owner : null,
        })),
        requiredConnectors: connectors.map((cid) => ({
          id: cid,
          name: cid.replace(/_/g, " "),
          connected: connectionState(cid),
        })),
        // The planner does not assign agents yet; an empty list is not a count.
        requiredAgents: agents > 0 ? agents : null,
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
  async function approve() {
    if (lock.current || !plan || !goalId) return
    lock.current = true
    setBusy("approve")
    setError(null)
    try {
      const response = await apiFetch(`/api/goals/${goalId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "active" }),
      })
      if (!response.ok)
        throw new Error(
          "Could not approve the plan. The goal and proposal stay saved as a draft; try again.",
        )
      onGoalSaved?.()
      setStep(4)
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not approve the plan. Try again.",
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
        department: deptLabel || undefined,
        connectors: systems.length ? systems : undefined,
        successMetric: metricLine || undefined,
        approvalRequired: plan.approvalGates.some((gate) => gate.required === true),
        orgContext: [
          deptLabel ? `Department: ${deptLabel}` : "",
          systems.length ? `Requested systems: ${systems.join(", ")}` : "",
          metricLine ? `Success metric: ${metricLine}` : "",
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

  const catalog = [...CONNECTOR_CATALOG].sort((a, b) => {
    const score = (key: string) =>
      (systems.includes(key) ? 2 : 0) + (connectionState(key) ? 1 : 0)
    return score(b.vendorKey) - score(a.vendorKey)
  })
  const visibleApps = showAllApps ? catalog : catalog.slice(0, VISIBLE_APPS)
  const deptAgents = (agentData?.agents ?? [])
    .filter((a) => departmentId(String(a.department ?? "")) === department)
    .slice(0, 3)
  const gateFor = (stepId: string) =>
    plan?.approvalGates.find((g) => g.stepId === stepId && g.required === true)
  const requiredGates = plan?.approvalGates.filter((g) => g.required === true).length ?? 0
  const done = step === 4
  const canReach = (n: number) =>
    !done && busy === null && (n === 1 || (n === 2 && Boolean(objective.trim())) || (n === 3 && Boolean(plan)))

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent
        showCloseButton={false}
        className="max-w-[1120px] gap-0 overflow-hidden rounded-[20px] border-0 p-0 sm:max-w-[min(1120px,calc(100%-2rem))]"
        data-composition="create"
      >
        <div className="gv-ws gv-ng">
          <div className="gv-ng-main">
            <div className="gv-ng-head">
              <div style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>
                <div style={{ flex: "1 1 auto", minWidth: 0 }}>
                  <p className="gv-eyebrow" style={{ margin: 0 }}>
                    Goals / {initialGoal ? "Continue setup" : "New business objective"}
                  </p>
                  <DialogTitle className="gv-ng-title">Start with the outcome</DialogTitle>
                  <DialogDescription className="gv-ng-desc">
                    Say what success looks like. Gravitre proposes a plan you
                    approve before any work runs.
                  </DialogDescription>
                </div>
                <button
                  type="button"
                  className="gv-iconbtn"
                  aria-label="Close"
                  disabled={busy !== null}
                  onClick={() => close(false)}
                >
                  <X className="size-5" />
                </button>
              </div>
              <ol aria-label="Goal creation steps" className="gv-ng-steps">
                {["Objective", "Context", "Review"].map((label, i) => {
                  const n = i + 1
                  const state = done || step > n ? "done" : step === n ? "on" : ""
                  return (
                    <li key={label} aria-current={step === n ? "step" : undefined}>
                      <button
                        type="button"
                        className={cn("gv-step", state)}
                        disabled={!canReach(n)}
                        onClick={() => setStep(n)}
                      >
                        <span className="n" aria-hidden>
                          {state === "done" ? "✓" : n}
                        </span>
                        {label}
                      </button>
                    </li>
                  )
                })}
              </ol>
            </div>

            <div className="gv-ng-body">
              <fieldset disabled={busy !== null} style={{ border: 0, margin: 0, padding: 0, minWidth: 0 }}>
                {step === 1 ? (
                  <div className="gv-ng-stack gv-rise">
                    <div>
                      <label className="gv-label" htmlFor="goal-objective">
                        What outcome do you want?
                      </label>
                      <textarea
                        id="goal-objective"
                        className="gv-textarea"
                        rows={3}
                        value={objective}
                        onChange={(e) => setObjective(e.target.value)}
                        placeholder="Get 100 MSP leads into HubSpot by December 31"
                      />
                      <div className="gv-ng-try">
                        <span className="gv-hint">Try</span>
                        {EXAMPLES.map((ex) => (
                          <button
                            key={ex}
                            type="button"
                            className="gv-opt try"
                            onClick={() => setObjective(ex)}
                          >
                            <span className="arrow" aria-hidden>
                              ↳
                            </span>
                            {ex}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div>
                      <span className="gv-label">
                        How will you measure it?{" "}
                        <span className="gv-hint">A number Gravitre can track from your data</span>
                      </span>
                      <div className="gv-ng-measure">
                        <label>
                          <span className="gv-hint">Metric</span>
                          <input
                            id="goal-metric"
                            className="gv-in"
                            value={metric}
                            onChange={(e) => setMetric(e.target.value)}
                            placeholder="MSP leads added to HubSpot"
                          />
                        </label>
                        <label>
                          <span className="gv-hint">Start</span>
                          <input
                            id="goal-start"
                            className="gv-in"
                            inputMode="decimal"
                            value={start}
                            onChange={(e) => setStart(e.target.value)}
                            placeholder="0"
                          />
                        </label>
                        <label>
                          <span className="gv-hint">Target</span>
                          <input
                            id="goal-target"
                            className="gv-in"
                            inputMode="decimal"
                            value={target}
                            onChange={(e) => setTarget(e.target.value)}
                            placeholder="100"
                          />
                        </label>
                        <label>
                          <span className="gv-hint">Due</span>
                          <input
                            id="goal-due"
                            className="gv-in"
                            type="date"
                            value={dueDate}
                            onChange={(e) => setDueDate(e.target.value)}
                          />
                        </label>
                      </div>
                    </div>
                    <div>
                      <span className="gv-label" id="goal-dept-label">
                        Department
                      </span>
                      <div role="group" aria-labelledby="goal-dept-label" style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                        {GOAL_DEPARTMENTS.map((d) => (
                          <button
                            key={d.id}
                            type="button"
                            className={cn("gv-opt", department === d.id && "on")}
                            aria-pressed={department === d.id}
                            onClick={() => setDepartment(department === d.id ? "" : d.id)}
                          >
                            <DepartmentGlyph department={d.id} size={14} />
                            {d.label}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="gv-ng-two">
                      <div>
                        <span className="gv-label">Priority</span>
                        <div className="gv-segwrap" role="group" aria-label="Priority">
                          {GOAL_PRIORITIES.map((p) => (
                            <button
                              key={p}
                              type="button"
                              className={cn("gv-segbtn", priority === p && "on")}
                              aria-pressed={priority === p}
                              onClick={() => setPriority(p)}
                            >
                              {capitalize(p)}
                            </button>
                          ))}
                        </div>
                      </div>
                      <div>
                        <span className="gv-label">Cadence</span>
                        <div className="gv-segwrap" role="group" aria-label="Cadence">
                          {GOAL_CADENCES.map((c) => (
                            <button
                              key={c}
                              type="button"
                              className={cn("gv-segbtn", frequency === c && "on")}
                              aria-pressed={frequency === c}
                              onClick={() => setFrequency(c)}
                            >
                              {capitalize(c)}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                ) : null}

                {step === 2 ? (
                  <div className="gv-ng-stack gv-rise" style={{ gap: 24 }}>
                    <div>
                      <span className="gv-label">
                        Where should Gravitre look and act?{" "}
                        <span className="gv-hint">
                          Planning context only. This does not connect an app or grant tool permissions.
                        </span>
                      </span>
                      {connectorLoading ? (
                        <p role="status" className="gv-hint">
                          Loading workspace connections...
                        </p>
                      ) : null}
                      {connectorError ? (
                        <div role="alert" className="gv-hint" style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", marginBottom: 10 }}>
                          Connection status is unavailable. You can still describe the requested systems.
                          <button type="button" className="gv-btn outline sm" onClick={() => void mutate()}>
                            Retry connections
                          </button>
                        </div>
                      ) : null}
                      <div className="gv-src-grid">
                        {visibleApps.map((c) => {
                          const state = connectionState(c.vendorKey)
                          const checked = systems.includes(c.vendorKey)
                          return (
                            <label key={c.vendorKey} className={cn("gv-src", checked && "on")}>
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={(e) =>
                                  setSystems((prev) =>
                                    e.target.checked
                                      ? [...prev, c.vendorKey]
                                      : prev.filter((v) => v !== c.vendorKey),
                                  )
                                }
                              />
                              <div style={{ flex: "1 1 auto", minWidth: 0 }}>
                                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                                  <strong style={{ fontWeight: 600 }}>{c.type}</strong>
                                  <span className={cn("gv-pill", state ? "brand" : "neutral")}>
                                    {state === null ? "Not reported" : state ? "Connected" : "Not connected"}
                                  </span>
                                </div>
                                {c.description ? (
                                  <div className="gv-hint" style={{ marginTop: 4 }}>
                                    {c.description.length > 110 ? `${c.description.slice(0, 107).trimEnd()}...` : c.description}
                                  </div>
                                ) : null}
                              </div>
                            </label>
                          )
                        })}
                      </div>
                      {catalog.length > VISIBLE_APPS ? (
                        <button
                          type="button"
                          className="gv-btn plain sm"
                          style={{ marginTop: 8 }}
                          onClick={() => setShowAllApps((v) => !v)}
                        >
                          {showAllApps ? "Show fewer apps" : `Show all ${catalog.length} apps`}
                        </button>
                      ) : null}
                    </div>

                    {department ? (
                      <div>
                        <span className="gv-label">Agents Gravitre suggests</span>
                        {deptAgents.length ? (
                          <div style={{ display: "grid", gap: 10 }}>
                            {deptAgents.map((a) => (
                              <div key={a.id} className="gv-ng-agent">
                                <DepartmentIcon department={a.department} size="md" />
                                <div style={{ flex: "1 1 auto", minWidth: 0 }}>
                                  <div style={{ fontWeight: 600 }}>{a.name}</div>
                                  <div className="gv-hint">{a.role || a.description || "Agent"}</div>
                                </div>
                                <span className="gv-pill brand">{deptLabel}</span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="gv-hint" style={{ margin: 0 }}>
                            {agentData
                              ? `No ${deptLabel} agents yet. The plan can still use workflows and Plays.`
                              : "Looking for agents in this department..."}
                          </p>
                        )}
                      </div>
                    ) : null}

                    <div>
                      <span className="gv-label">Always pause before</span>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                        <span className="gv-opt on static">
                          <Lock className="size-4" aria-hidden />
                          Writing to the CRM · policy
                        </span>
                        {PAUSE_OPTIONS.map((p) => {
                          const on = pauseBefore.includes(p.id)
                          return (
                            <button
                              key={p.id}
                              type="button"
                              className={cn("gv-opt", on && "on")}
                              aria-pressed={on}
                              onClick={() =>
                                setPauseBefore((prev) =>
                                  on ? prev.filter((v) => v !== p.id) : [...prev, p.id],
                                )
                              }
                            >
                              {p.label}
                            </button>
                          )
                        })}
                      </div>
                    </div>

                    <div>
                      <label className="gv-label" htmlFor="goal-notes">
                        Anything the agents should know? <span className="gv-hint">Optional</span>
                      </label>
                      <textarea
                        id="goal-notes"
                        className="gv-textarea"
                        style={{ fontSize: 15, minHeight: 84 }}
                        value={notes}
                        onChange={(e) => setNotes(e.target.value)}
                        placeholder="Who counts as a customer for us, regions to focus on, accounts to skip"
                      />
                    </div>
                  </div>
                ) : null}

                {step === 3 && plan ? (
                  <div className="gv-ng-stack gv-rise" style={{ gap: 18 }}>
                    <div className="gv-ng-banner">
                      <span className="gv-ng-spark" aria-hidden>
                        <Sparkles className="size-3.5" />
                      </span>
                      <span>
                        Gravitre drafted this plan from your outcome and context. The goal
                        and proposal are saved. Nothing runs until you approve.
                      </span>
                    </div>
                    {plan.steps.length ? (
                      <ol className="gv-ng-plan">
                        {plan.steps.map((s, i) => {
                          const gate = gateFor(s.id)
                          const blocked = s.status && !["planned", "ready", "task"].includes(s.status)
                          return (
                            <li key={s.id}>
                              <span className={cn("gv-ng-num", blocked && "warn")}>{i + 1}</span>
                              <div style={{ flex: "1 1 auto", minWidth: 0 }}>
                                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                                  <span style={{ fontWeight: 600 }}>{s.name}</span>
                                  {gate ? <span className="gv-pill amber">Approval gate</span> : null}
                                </div>
                                {s.description && s.description !== s.name ? (
                                  <div className="gv-hint" style={{ marginTop: 3 }}>
                                    {s.description}
                                  </div>
                                ) : s.owner ? (
                                  <div className="gv-hint" style={{ marginTop: 3 }}>
                                    {capitalize(s.owner)}
                                  </div>
                                ) : null}
                                {blocked ? (
                                  <div className="gv-ng-warn">
                                    {capitalize(String(s.status).replace(/_/g, " "))}
                                  </div>
                                ) : null}
                              </div>
                            </li>
                          )
                        })}
                      </ol>
                    ) : (
                      <p className="gv-hint" style={{ margin: 0 }}>
                        Proposed steps not reported.
                      </p>
                    )}
                    <div className="gv-ng-stats">
                      <div className="gv-ng-stat">
                        <div className="gv-eyebrow">Agents</div>
                        <div className={cn("v", plan.requiredAgents === null && "unreported")}>
                          {plan.requiredAgents ?? "Not reported"}
                        </div>
                      </div>
                      <div className="gv-ng-stat">
                        <div className="gv-eyebrow">Apps</div>
                        <div className="v">{plan.requiredConnectors.length}</div>
                      </div>
                      <div className={cn("gv-ng-stat", requiredGates > 0 && "amber")}>
                        <div className="gv-eyebrow">Approval gates</div>
                        <div className="v">{requiredGates}</div>
                      </div>
                    </div>
                    <div className="gv-ng-detail">
                      <dl className="gv-dl">
                        <dt>Estimated runtime</dt>
                        <dd>{plan.estimatedRuntime ?? "Not reported"}</dd>
                        <dt>Reported risk</dt>
                        <dd>{plan.riskLevel ?? "Not reported"}</dd>
                        <dt>Required systems</dt>
                        <dd>
                          {plan.requiredConnectors.length
                            ? plan.requiredConnectors.map((c) => (
                                <p key={c.id}>
                                  {c.name} ·{" "}
                                  {c.connected === null
                                    ? "Connection not reported"
                                    : c.connected
                                      ? "Connected"
                                      : "Not connected"}
                                </p>
                              ))
                            : "No required systems returned."}
                        </dd>
                        <dt>Approval policy</dt>
                        <dd>
                          {plan.approvalGates.length
                            ? plan.approvalGates.map((g) => (
                                <p key={g.stepId}>
                                  {capitalize(g.reason.replace(/[-_]/g, " "))} ·{" "}
                                  {g.required === null
                                    ? "Requirement not reported"
                                    : g.required
                                      ? "Required"
                                      : "Not required by this proposal"}
                                </p>
                              ))
                            : "Approval requirements not reported."}
                        </dd>
                      </dl>
                      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                        <button type="button" className="gv-btn outline sm" onClick={() => void run("plan")}>
                          <RefreshCw className="size-4" aria-hidden />
                          Regenerate
                        </button>
                        {goalId ? (
                          <button type="button" className="gv-btn outline sm" onClick={() => void openBuilder()}>
                            Open workflow builder
                          </button>
                        ) : null}
                        {goalId ? (
                          <Link
                            className="gv-btn plain sm"
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
                        ) : null}
                      </div>
                    </div>
                  </div>
                ) : null}

                {done ? (
                  <div className="gv-ng-done gv-rise">
                    {/* eslint-disable-next-line @next/next/no-img-element -- static SVG scene */}
                    <img src="/illustrations/moment-high-five.svg" alt="" data-illustration="moment-high-five" />
                    <h2>Plan approved. Your goal is in motion.</h2>
                    <p>
                      Steps that write to your systems pause in the Decision queue
                      before they happen.
                    </p>
                    <div style={{ display: "flex", gap: 10, marginTop: 22, flexWrap: "wrap", justifyContent: "center" }}>
                      <button type="button" className="gv-btn primary" onClick={() => close(false)}>
                        Go to Goals
                      </button>
                      <Link className="gv-btn ghost" href="/approvals" onClick={() => close(false)}>
                        Open Decision queue
                      </Link>
                    </div>
                  </div>
                ) : null}
              </fieldset>
              {busy ? (
                <p role="status" className="gv-ng-busy">
                  <Loader2 className="size-4 animate-spin motion-reduce:animate-none" />
                  {busy === "plan"
                    ? "Waiting for the planner's response..."
                    : busy === "build"
                      ? "Creating the workflow..."
                      : busy === "approve"
                        ? "Approving the plan..."
                        : "Saving goal..."}
                </p>
              ) : null}
              {error ? (
                <p role="alert" className="gv-ng-error">
                  {error}
                </p>
              ) : null}
            </div>

            {!done ? (
              <div className="gv-ng-foot">
                {step > 1 ? (
                  <button
                    type="button"
                    className="gv-btn plain"
                    disabled={busy !== null}
                    onClick={() => setStep(step - 1)}
                  >
                    <ArrowLeft className="size-4" aria-hidden />
                    Back
                  </button>
                ) : (
                  <button
                    type="button"
                    className="gv-btn plain"
                    disabled={busy !== null}
                    onClick={() => close(false)}
                  >
                    Cancel
                  </button>
                )}
                <span className="meta">
                  Step {step} of 3 · {goalId ? "Saved as a draft" : "Save a draft any time"}
                </span>
                <span className="grow" />
                <button
                  type="button"
                  className="gv-btn ghost"
                  disabled={busy !== null || !objective.trim()}
                  onClick={() => void run("save")}
                >
                  Save draft
                </button>
                {step === 1 ? (
                  <button
                    type="button"
                    className="gv-btn primary"
                    disabled={!objective.trim() || busy !== null}
                    onClick={() => setStep(2)}
                  >
                    Continue
                    <ArrowRight className="size-4" aria-hidden />
                  </button>
                ) : step === 2 ? (
                  <button
                    type="button"
                    className="gv-btn primary"
                    disabled={busy !== null || !objective.trim()}
                    onClick={() => void run("plan")}
                  >
                    Generate plan
                  </button>
                ) : (
                  <button
                    type="button"
                    className="gv-btn primary"
                    disabled={busy !== null || !plan || !goalId}
                    onClick={() => void approve()}
                  >
                    Approve plan and start
                    <ArrowRight className="size-4" aria-hidden />
                  </button>
                )}
              </div>
            ) : null}
          </div>

          <aside className="gv-ng-aside" aria-label="Live preview">
            <div className="gv-eyebrow">Live preview</div>
            <div className="gv-ng-preview">
              {department ? (
                // eslint-disable-next-line @next/next/no-img-element -- static SVG scene
                <img
                  src={`/illustrations/dept-${department}.svg`}
                  alt=""
                  data-illustration={`dept-${department}`}
                />
              ) : (
                <div className="gv-ng-preview-blank">Pick a department to see its scene here</div>
              )}
              <div style={{ padding: 18 }}>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  <span className="gv-pill neutral">{done ? "In motion" : "Draft"}</span>
                  {deptLabel ? <span className="gv-pill brand">{deptLabel}</span> : null}
                  <span className="gv-pill outline">
                    {capitalize(priority)} · {capitalize(frequency)}
                  </span>
                </div>
                <div className={cn("gv-ng-preview-title", !objective.trim() && "empty")}>
                  {objective.trim() || "Your outcome appears here"}
                </div>
                {metric.trim() || target.trim() ? (
                  <div className="gv-hint" style={{ marginTop: 6 }}>
                    {[
                      target.trim() ? `Target ${target.trim()}` : "",
                      metric.trim(),
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    {dueDate ? ` · due ${dueDate}` : ""}
                  </div>
                ) : null}
                <div className="gv-ng-bar" />
              </div>
            </div>
            <div>
              <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 10 }}>Is it a strong goal?</div>
              <ul className="gv-ng-checks">
                {checks.map((k) => (
                  <li key={k.id}>
                    <span className={cn("gv-ng-mark", k.ok && "ok")} aria-hidden>
                      {k.ok ? "✓" : "!"}
                    </span>
                    <span>
                      <strong style={{ fontWeight: 600 }}>{k.label}</strong>{" "}
                      <span style={{ color: "var(--gv-muted)" }}>{k.note}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
            <p className="gv-ng-tip">
              Goals with one number and one date get sharper plans and cleaner
              progress tracking. Keep the sentence short; put context in step 2.
            </p>
          </aside>
        </div>
      </DialogContent>
    </Dialog>
  )
}
