"use client"

import { useEffect, useMemo, useRef, useState, type FormEvent, type RefObject } from "react"
import { DepartmentIcon } from "@/components/agents/department-icon"
import { useAgentDepartments } from "@/lib/use-agent-departments"
import Link from "next/link"
import useSWR from "swr"
import { toast } from "sonner"
import { AlertTriangle, ChevronDown, Sparkle } from "lucide-react"
import { agentsApi, marketplaceApi } from "@/lib/api"
import { avatarGradient, createAssignment } from "@/lib/assignments"
import type { DemoAssignment } from "@/lib/demo-assignments"
import { collectInstalledAgentIds, resolveDefaultAgentId } from "@/lib/resolve-default-agent"
import { shortDate } from "@/lib/assignment-signals"

export type LaneId = "queued" | "running" | "waiting" | "delivered"

export const LANES: Array<{ id: LaneId; label: string; empty: string }> = [
  { id: "queued", label: "Queued", empty: "Nothing queued. New assignments wait here for a free agent." },
  { id: "running", label: "Executing", empty: "No agent working" },
  { id: "waiting", label: "Waiting on you", empty: "Assignments pause here when they need your input or an approval." },
  { id: "delivered", label: "Delivered", empty: "Finished assignments land here with their outcome." },
]

export function laneOf(assignment: DemoAssignment): LaneId {
  if (assignment.status === "running") return "running"
  if (assignment.status === "needs_approval") return "waiting"
  if (assignment.status === "completed" || assignment.status === "failed") return "delivered"
  return "queued"
}

export function laneLabel(lane: LaneId): string {
  return LANES.find((item) => item.id === lane)?.label ?? "Assignments"
}

const MIN_BRIEF = 10

/** Inline composer: describe the work, pick a real agent, Assign (Enter submits). */
export function AssignComposer({
  inputRef,
  onCreated,
}: {
  inputRef: RefObject<HTMLInputElement | null>
  onCreated: (assignment: DemoAssignment) => void
}) {
  const agentRequest = useSWR("assignment-agents", () => agentsApi.list(), { revalidateOnFocus: false })
  const installRequest = useSWR(
    "assignment-installs",
    () => marketplaceApi.listInstalls({ status: "active", limit: 100 }),
    { revalidateOnFocus: false },
  )
  const agents = useMemo(() => {
    const all = agentRequest.data?.agents ?? []
    const active = all.filter((agent) => !agent.status || agent.status === "active")
    return active.length > 0 ? active : all
  }, [agentRequest.data?.agents])
  const [agentId, setAgentId] = useState<string | null>(null)
  const [text, setText] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const resolved = useRef(false)

  useEffect(() => {
    if (resolved.current || agentRequest.isLoading || installRequest.isLoading || agents.length === 0) return
    resolved.current = true
    setAgentId(
      resolveDefaultAgentId({
        agents,
        installedAgentIds: collectInstalledAgentIds(installRequest.data?.installs ?? []),
      }),
    )
  }, [agents, agentRequest.isLoading, installRequest.isLoading, installRequest.data])

  const agent = agents.find((item) => item.id === agentId) ?? null
  const noAgents = !agentRequest.isLoading && agents.length === 0

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (submitting) return
    const task = text.trim()
    if (!agent) {
      setError(noAgents ? "Add an agent first, then assign it work." : "Pick an agent for this work.")
      return
    }
    if (task.length < MIN_BRIEF) {
      setError("Describe the work in a sentence so the agent knows what done looks like.")
      inputRef.current?.focus()
      return
    }
    setError(null)
    setSubmitting(true)
    try {
      const { assignment } = await createAssignment({
        agentId: agent.id,
        agentName: agent.name,
        agentRole: agent.role || agent.description || "Agent",
        agentGradient: avatarGradient(agent.personality?.color ?? ""),
        task,
        priority: "normal",
      })
      setText("")
      onCreated({ ...assignment, agentId: agent.id })
      toast.success("Assignment queued. It starts as soon as the agent is free.")
    } catch (err) {
      setError(err instanceof Error ? err.message : "The assignment could not be created.")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section id="assign" className="gv-rise" aria-label="Assign new work">
      <form className="gv-card asg-composer" onSubmit={(event) => void submit(event)}>
        <Sparkle aria-hidden size={20} className="asg-composer-spark" />
        <label htmlFor="gvAssign" className="sr-only">
          Describe the work
        </label>
        <input
          id="gvAssign"
          ref={inputRef}
          className="asg-composer-input"
          placeholder="Describe the work, for example: enrich the 40 newest HubSpot contacts"
          value={text}
          onChange={(event) => {
            setText(event.target.value)
            if (error) setError(null)
          }}
          disabled={submitting}
          autoComplete="off"
        />
        <span className="gv-chip asg-agentchip">
          <DepartmentIcon department={agent?.department} size="xs" />
          <span className="asg-agentchip-name">
            {agent?.name ?? (agentRequest.isLoading ? "Loading agents" : noAgents ? "No agents yet" : "Pick an agent")}
          </span>
          <ChevronDown aria-hidden size={14} />
          <select
            aria-label="Agent"
            value={agentId ?? ""}
            onChange={(event) => setAgentId(event.target.value || null)}
            disabled={agents.length === 0 || submitting}
          >
            {agentId ? null : <option value="">Pick an agent</option>}
            {agents.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </span>
        <button type="submit" className="gv-btn dark asg-assign" disabled={submitting || noAgents}>
          {submitting ? "Assigning" : "Assign"} <span className="asg-enter" aria-hidden>↵</span>
        </button>
      </form>
      {error ? (
        <p role="alert" className="asg-composer-error">
          {error}
          {noAgents ? (
            <>
              {" "}
              <Link href="/agents">Go to agents</Link>
            </>
          ) : null}
        </p>
      ) : null}
      <div className="asg-composer-note">
        <span>Every write to an app pauses in the</span>
        <Link href="/approvals">Decision queue</Link>
        <span>before it runs.</span>
      </div>
    </section>
  )
}

function FlagPill({ flag }: { flag: NonNullable<DemoAssignment["flag"]> }) {
  return (
    <span className={`gv-pill ${flag.tone}`}>
      {flag.needsLook ? <AlertTriangle aria-hidden size={12} strokeWidth={2.4} /> : null}
      {flag.label}
    </span>
  )
}

function statusPill(assignment: DemoAssignment): { label: string; tone: string } | null {
  if (assignment.jobStatus === "paused") return { label: "Paused", tone: "neutral" }
  if (assignment.status === "needs_approval") return { label: "Needs your decision", tone: "amber" }
  return null
}

function cardSummary(assignment: DemoAssignment): string | null {
  if (assignment.status === "needs_approval") return assignment.approvalPrompt ?? "The agent paused for your decision before continuing."
  if (assignment.status === "failed") return assignment.blocker ?? "The job stopped without reporting a reason."
  if (assignment.status === "completed") return assignment.resultSummary ?? (assignment.flag?.needsLook ? assignment.blocker ?? null : null)
  if (assignment.status === "running") return assignment.currentStepDetail ?? null
  return null
}

export function AssignmentCard({ assignment }: { assignment: DemoAssignment }) {
  const departmentOf = useAgentDepartments()
  const summary = cardSummary(assignment)
  const pill = statusPill(assignment)
  const progress =
    assignment.status === "running" && Number.isFinite(assignment.progress) ? Math.max(0, Math.min(100, assignment.progress)) : null
  const actions = assignment.actions
  const hasStats = Boolean(actions) || typeof assignment.confidence === "number"
  const date = shortDate(assignment.createdAtIso ?? assignment.createdAt) || assignment.createdAt
  return (
    <li>
      <Link
        href={assignment.status === "needs_approval" ? `/assignments/${assignment.id}?approval=1` : `/assignments/${assignment.id}`}
        className="asg-card gv-rise"
        data-assignment-id={assignment.id}
      >
        {assignment.flag || pill ? (
          <div className="asg-card-flags">
            {pill ? <span className={`gv-pill ${pill.tone}`}>{pill.label}</span> : null}
            {assignment.flag ? <FlagPill flag={assignment.flag} /> : null}
          </div>
        ) : null}
        <div className="asg-card-title">{assignment.title}</div>
        {summary ? <div className="asg-card-summary">{summary}</div> : null}
        {assignment.status === "running" ? (
          <div className="asg-card-live">
            <span className="gv-ping" style={{ background: "var(--gv-accent)" }} aria-hidden />
            {progress !== null ? `${progress}% reported` : "Working now"}
          </div>
        ) : null}
        {hasStats ? (
          <div className="asg-stats">
            {actions ? (
              actions.failed > 0 ? (
                <div className="asg-stat">
                  <div className="asg-stat-label">Actions failed</div>
                  <div className="asg-stat-value bad">
                    {actions.failed} of {actions.total}
                  </div>
                </div>
              ) : (
                <div className="asg-stat">
                  <div className="asg-stat-label">Actions succeeded</div>
                  <div className="asg-stat-value good">
                    {actions.succeeded} of {actions.total}
                  </div>
                </div>
              )
            ) : null}
            {typeof assignment.confidence === "number" ? (
              <div className="asg-stat">
                <div className="asg-stat-label">Confidence</div>
                <div className="asg-stat-value">{assignment.confidence}%</div>
              </div>
            ) : null}
          </div>
        ) : null}
        <div className="asg-card-foot">
          <DepartmentIcon department={departmentOf({ id: assignment.agentId, name: assignment.agent.name })} size="xs" />
          <span className="asg-agentname">{assignment.agent.name}</span>
          {date ? <span className="asg-date">{date}</span> : null}
        </div>
      </Link>
    </li>
  )
}

export function BoardLanes({ byLane }: { byLane: Map<LaneId, DemoAssignment[]> }) {
  return (
    <section aria-label="Board" className="asg-board" data-assignments-track="">
      {LANES.map((lane) => {
        const items = byLane.get(lane.id) ?? []
        return (
          <div key={lane.id} className={`asg-lane ${lane.id}`} data-assignment-phase={lane.id}>
            <h2 className="asg-lanehead" id={`lane-${lane.id}`}>
              <span className={`asg-dot ${lane.id}`} aria-hidden />
              {lane.label}
              <span className="asg-lanecount">{items.length}</span>
            </h2>
            {items.length > 0 ? (
              <ul className="asg-lanelist" aria-labelledby={`lane-${lane.id}`}>
                {items.map((assignment) => (
                  <AssignmentCard key={assignment.id} assignment={assignment} />
                ))}
              </ul>
            ) : lane.id === "running" ? (
              <div className="asg-lane-illus">
                {/* eslint-disable-next-line @next/next/no-img-element -- static library illustration */}
                <img src="/illustrations/moment-paused-agents.svg" alt="" data-illustration="moment-paused-agents" />
                <div className="asg-lane-illus-title">No agent working</div>
                <div className="asg-lane-illus-body">Describe a job above and it starts here, live.</div>
              </div>
            ) : (
              <div className="gv-empty">{lane.empty}</div>
            )}
          </div>
        )
      })}
    </section>
  )
}

export function AssignmentListView({ byLane }: { byLane: Map<LaneId, DemoAssignment[]> }) {
  return (
    <section aria-label="Assignments list" className="gv-card asg-list" data-assignments-list="">
      {LANES.map((lane) => {
        const items = byLane.get(lane.id) ?? []
        return (
          <div key={lane.id} className="asg-list-group">
            <h2 className="asg-list-grouphead" id={`list-${lane.id}`}>
              <span className={`asg-dot ${lane.id}`} aria-hidden />
              {lane.label}
              <span className="asg-lanecount">{items.length}</span>
            </h2>
            {items.length === 0 ? (
              <p className="asg-list-empty">{lane.id === "running" ? "No agent working right now." : lane.empty}</p>
            ) : (
              <ul className="asg-list-rows" aria-labelledby={`list-${lane.id}`}>
                {items.map((assignment) => {
                  const summary = cardSummary(assignment)
                  const pill = statusPill(assignment)
                  const date = shortDate(assignment.createdAtIso ?? assignment.createdAt) || assignment.createdAt
                  return (
                    <li key={assignment.id}>
                      <Link
                        href={
                          assignment.status === "needs_approval"
                            ? `/assignments/${assignment.id}?approval=1`
                            : `/assignments/${assignment.id}`
                        }
                        className="asg-list-row"
                        data-assignment-id={assignment.id}
                      >
                        <div className="asg-list-main">
                          <div className="asg-list-title">{assignment.title}</div>
                          {summary ? <div className="asg-list-sub">{summary}</div> : null}
                        </div>
                        <div className="asg-list-meta">
                          {pill ? <span className={`gv-pill ${pill.tone}`}>{pill.label}</span> : null}
                          {assignment.flag ? <FlagPill flag={assignment.flag} /> : null}
                          {assignment.actions && assignment.actions.failed > 0 ? (
                            <span>
                              {assignment.actions.failed} of {assignment.actions.total} actions failed
                            </span>
                          ) : null}
                          {typeof assignment.confidence === "number" ? <span>{assignment.confidence}% confidence</span> : null}
                          <span>{assignment.agent.name}</span>
                          {date ? <span>{date}</span> : null}
                        </div>
                      </Link>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        )
      })}
    </section>
  )
}
