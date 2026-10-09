"use client"

// Agents > Instructions ("Gravitre Agents" design): guidance and guardrails for one
// agent, a department or the whole team, on /api/training/instructions.
import { useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { toast } from "sonner"
import { useSearchParams } from "next/navigation"
import { AgentsHubTabs } from "@/components/agents/agents-hub-tabs"
import { useGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { WsPage } from "@/components/workspace/ws-page"
import { DepartmentGlyph } from "@/components/agents/department-icon"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import "@/components/agents/roster/roster.css"
import "@/components/agents/suite/agents-suite.css"
import type { AgentDepartmentId } from "@/components/agents/fleet-v4/types"
import { trainingApi } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import { useAuth } from "@/lib/auth-context"
import { fetcher as apiFetcher, formatUnknownError } from "@/lib/fetcher"
import { ensureSelectedOrg } from "@/lib/org-context"
import { DEPARTMENT_BY_ID, ROSTER_DEPARTMENTS, normalizeAgentsPayload, toRosterAgent } from "@/lib/agents-roster"
import type { CustomInstruction, CustomInstructionKind } from "@/types/api"
import { cn } from "@/lib/utils"

/** "all" = whole team, "agent" = one agent, otherwise a roster department id. */
type Scope = "all" | "agent" | AgentDepartmentId
type ListFilter = "all" | CustomInstructionKind

const ALL_DOT = "#2e9e5b"

const TEMPLATES: Array<{ name: string; kind: CustomInstructionKind; scope: "all" | AgentDepartmentId; text: string }> = [
  {
    name: "Confirm before emailing customers",
    kind: "guardrail",
    scope: "all",
    text: "Agents may draft customer emails but never send one until a person approves it.",
  },
  {
    name: "Protect pricing floors",
    kind: "guardrail",
    scope: "sales",
    text: "Never quote below [approved floor] or promise a discount without sign off.",
  },
  {
    name: "Escalation tone",
    kind: "guidance",
    scope: "customer_success",
    text: "When a customer is upset, acknowledge the problem first, then offer one clear next step.",
  },
  {
    name: "Read only finance data",
    kind: "guardrail",
    scope: "finance",
    text: "Read ledgers and reports freely. Never create, edit or delete an entry.",
  },
  {
    name: "Cite your sources",
    kind: "guidance",
    scope: "all",
    text: "Every recommendation lists the records, reports or pages it relied on.",
  },
  {
    name: "House writing style",
    kind: "guidance",
    scope: "marketing",
    text: "Plain language, short sentences, no jargon. Sign off as the team, never as an AI.",
  },
]

function deptName(id: string) {
  return DEPARTMENT_BY_ID.get(id as AgentDepartmentId)?.name ?? id
}

function kindOf(i: CustomInstruction): CustomInstructionKind {
  return i.kind === "guardrail" ? "guardrail" : "guidance"
}

function relativeUpdate(ms: number | null) {
  if (!ms) return "Not loaded yet"
  const minutes = Math.round((Date.now() - ms) / 60000)
  if (minutes < 1) return "Updated just now"
  if (minutes < 60) return `Updated ${minutes} min ago`
  return `Updated ${Math.round(minutes / 60)} h ago`
}

function formatDate(iso?: string) {
  if (!iso) return null
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? null : d.toLocaleDateString(undefined, { month: "short", day: "numeric" })
}

export function InstructionsPage() {
  const { user } = useAuth()
  const searchParams = useSearchParams()
  const { summonWorkspace, pageContext } = useGravitreAIWorkspace()
  const formRef = useRef<HTMLElement>(null)
  const nameRef = useRef<HTMLInputElement>(null)
  const [orgReady, setOrgReady] = useState(false)
  const [orgError, setOrgError] = useState<string | null>(null)
  const [orgAttempt, setOrgAttempt] = useState(0)

  const initialAgent = searchParams.get("agentId") ?? ""
  const [name, setName] = useState("")
  const [content, setContent] = useState("")
  const [kind, setKind] = useState<CustomInstructionKind>("guidance")
  const [scope, setScope] = useState<Scope>(initialAgent ? "agent" : "all")
  const [agentId, setAgentId] = useState(initialAgent)
  const [enabled, setEnabled] = useState(true)
  const [template, setTemplate] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<CustomInstruction | null>(null)
  const [filter, setFilter] = useState<ListFilter>("all")
  const [updatedAt, setUpdatedAt] = useState<number | null>(null)
  const [, tick] = useState(0)

  useEffect(() => {
    let cancelled = false
    setOrgReady(false)
    setOrgError(null)
    if (user)
      void ensureSelectedOrg(true)
        .then((id) => {
          if (cancelled) return
          setOrgReady(Boolean(id))
          if (!id) setOrgError("Workspace membership is required to load instructions.")
        })
        .catch(() => {
          if (!cancelled) setOrgError("Could not load your workspace. Try again.")
        })
    return () => {
      cancelled = true
    }
  }, [user, orgAttempt])

  useEffect(() => {
    const id = window.setInterval(() => tick((n) => n + 1), 60_000)
    return () => window.clearInterval(id)
  }, [])

  const {
    data,
    error,
    isLoading,
    isValidating,
    mutate,
  } = useSWR(orgReady ? "training/instructions" : null, () => trainingApi.listInstructions(), {
    onSuccess: () => setUpdatedAt(Date.now()),
  })
  const { data: agentsData, mutate: mutateAgents } = useSWR(user ? "/api/agents" : null, apiFetcher, {
    dedupingInterval: 2000,
  })

  const agents = useMemo(
    () =>
      normalizeAgentsPayload(agentsData)
        .map((raw) => toRosterAgent(raw, undefined))
        .sort((a, b) => a.name.localeCompare(b.name)),
    [agentsData],
  )
  const agentById = useMemo(() => new Map(agents.map((a) => [a.id, a])), [agents])
  const deptCounts = useMemo(() => {
    const counts = new Map<AgentDepartmentId, number>()
    for (const a of agents) counts.set(a.department, (counts.get(a.department) ?? 0) + 1)
    return counts
  }, [agents])

  const instructions = useMemo(() => data?.instructions ?? [], [data])
  const counts = useMemo(() => {
    const guardrail = instructions.filter((i) => kindOf(i) === "guardrail").length
    return { all: instructions.length, guardrail, guidance: instructions.length - guardrail }
  }, [instructions])
  const visible = useMemo(
    () => (filter === "all" ? instructions : instructions.filter((i) => kindOf(i) === filter)),
    [instructions, filter],
  )

  // Departments shown as scope chips: every department you have agents in, in roster order.
  const scopeDepts = useMemo(
    () => ROSTER_DEPARTMENTS.filter((d) => (deptCounts.get(d.id) ?? 0) > 0 || d.id === scope),
    [deptCounts, scope],
  )

  const total = agents.length
  const chosenAgent = scope === "agent" ? agentById.get(agentId) ?? null : null
  const who =
    scope === "all"
      ? `all ${total} ${total === 1 ? "agent" : "agents"}`
      : scope === "agent"
        ? chosenAgent
          ? chosenAgent.name
          : "the agent you choose"
        : (() => {
            const n = deptCounts.get(scope) ?? 0
            const label = deptName(scope)
            return n === 1 ? `the 1 ${label} agent` : `the ${n} ${label} agents`
          })()
  const when = enabled ? "starting on their next run." : "once you switch it on."
  const summary =
    kind === "guardrail"
      ? `This guardrail will bind ${who}, ${when} Agents stop and ask you before crossing it.`
      : `This guidance will be added to ${who}, ${when}`

  const canSave = orgReady && name.trim() && content.trim() && (scope !== "agent" || Boolean(chosenAgent)) && !saving

  function applyTemplate(t: (typeof TEMPLATES)[number]) {
    setKind(t.kind)
    setScope(t.scope)
    setName(t.name)
    setContent(t.text)
    setTemplate(t.name)
    setFormError(null)
    formRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
    window.setTimeout(() => nameRef.current?.focus({ preventScroll: true }), 300)
  }

  async function create() {
    if (!canSave) return
    setSaving(true)
    setFormError(null)
    try {
      await trainingApi.createInstruction({
        name: name.trim(),
        content: content.trim(),
        kind,
        agent_id: scope === "agent" ? agentId : undefined,
        department: scope !== "all" && scope !== "agent" ? scope : null,
        is_active: enabled,
      })
      toast.success(kind === "guardrail" ? "Guardrail created" : "Instruction created")
      setName("")
      setContent("")
      setTemplate(null)
      await mutate()
    } catch (err) {
      setFormError(formatUnknownError(err, "Could not save this instruction. Your text is kept; try again."))
    } finally {
      setSaving(false)
    }
  }

  async function toggle(i: CustomInstruction) {
    if (busyId) return
    setBusyId(i.id)
    try {
      await trainingApi.toggleInstruction(i.id, !i.is_active)
      toast.success(i.is_active ? "Switched off" : "Switched on")
      await mutate()
    } catch (err) {
      toast.error(formatUnknownError(err, "Could not update this instruction"))
    } finally {
      setBusyId(null)
    }
  }

  async function remove(i: CustomInstruction) {
    setBusyId(i.id)
    try {
      await trainingApi.deleteInstruction(i.id)
      setDeleteTarget(null)
      toast.success("Instruction deleted")
      await mutate()
    } catch (err) {
      toast.error(formatUnknownError(err, "Could not delete this instruction"))
    } finally {
      setBusyId(null)
    }
  }

  function scopeLabel(i: CustomInstruction): { label: string; department: string | null } {
    if (i.agent_id) {
      const agent = agentById.get(i.agent_id)
      return { label: i.agent_name ?? agent?.name ?? "One agent", department: agent?.department ?? null }
    }
    if (i.department) return { label: deptName(i.department), department: i.department }
    return { label: "All agents", department: null }
  }

  return (
    <WsPage>
      <div className="rs-tabs">
        <AgentsHubTabs active="training" />
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 24, paddingTop: 24 }}>
        <section aria-labelledby="in-hero" className="as-panel in-hero">
          <div className="in-hero-art">
            {/* eslint-disable-next-line @next/next/no-img-element -- static library scene */}
            <img
              src="/illustrations/agents-guardrails.svg"
              alt="A business lead at a large screen setting the rules for an AI system inside a protective shield"
            />
          </div>
          <div className="in-hero-copy">
            <div className="in-hero-eb">
              <span className="eb">Guidance and guardrails</span>
              <span className="in-updated">
                <i />
                {relativeUpdate(updatedAt)}
              </span>
            </div>
            <h1 id="in-hero">Instructions</h1>
            <p>
              Standing rules your agents follow on every run, including council runs. Point one at a single agent, a
              department or the whole team.
            </p>
            <div className="in-kinds">
              <div className="in-kind guidance">
                <b>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                    <path d="M4 19V5a2 2 0 0 1 2-2h12v18H6a2 2 0 0 1-2-2z" />
                    <path d="M8 7h6M8 11h6" />
                  </svg>
                  Guidance
                </b>
                <span>Shapes how agents work: tone, format, when to escalate.</span>
              </div>
              <div className="in-kind guardrail">
                <b>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                    <path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" />
                  </svg>
                  Guardrail
                </b>
                <span>A hard limit. If an agent would cross it, it stops and asks you first.</span>
              </div>
            </div>
            <div className="ma-actions">
              <button
                type="button"
                className="gv-btn dark"
                onClick={() =>
                  summonWorkspace({
                    presentation: "compact",
                    selected: pageContext.selected,
                    agentScope: null,
                    composerText:
                      "Help me plan instructions for my agents: which guardrails to add for anything touching customers or money, and what guidance each department needs.",
                    submit: false,
                  })
                }
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" aria-hidden>
                  <path d="M12 3l2.2 5.8L20 11l-5.8 2.2L12 19l-2.2-5.8L4 11l5.8-2.2z" />
                </svg>
                Plan instructions with Gravitre
              </button>
              <button
                type="button"
                className="gv-btn outline"
                disabled={!orgReady || isValidating}
                onClick={() => {
                  void mutate()
                  void mutateAgents()
                }}
              >
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden
                  className={cn(isValidating && "animate-spin motion-reduce:animate-none")}
                >
                  <path d="M21 12a9 9 0 1 1-3-6.7L21 8" />
                  <path d="M21 3v5h-5" />
                </svg>
                Refresh
              </button>
            </div>
          </div>
        </section>

        <div className="as-info">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
            <circle cx="12" cy="12" r="9" />
            <path d="M12 11v5M12 8h.01" />
          </svg>
          <span>
            Looking for datasets or fine-tunes? They now live in{" "}
            <Link href={APP_ROUTES.intelligenceData}>Intelligence › Data</Link> and{" "}
            <Link href={`${APP_ROUTES.models}#training`}>Models</Link>.
          </span>
        </div>

        {orgError ? (
          <WorkSectionErrorCard
            title="Could not load workspace"
            message={orgError}
            onRetry={() => setOrgAttempt((n) => n + 1)}
          />
        ) : null}

        <div className="in-row">
          <section ref={formRef} aria-labelledby="new-heading" className="as-panel in-form" style={{ scrollMarginTop: 80 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <h2 id="new-heading">New instruction</h2>
              <p className="as-copy">Added to each chosen agent&apos;s system prompt while it is switched on. No fine-tune needed.</p>
            </div>
            {template ? (
              <div className="in-from-tpl">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
                  <path d="M5 12l5 5 9-10" />
                </svg>
                Started from the template &ldquo;{template}&rdquo;. Edit anything before you save.
              </div>
            ) : null}

            <div>
              <label htmlFor="in-name" className="gv-label">
                Name
              </label>
              <input
                ref={nameRef}
                id="in-name"
                type="text"
                className="gv-in"
                placeholder="For example: Escalation tone"
                value={name}
                maxLength={120}
                onChange={(e) => setName(e.target.value)}
              />
            </div>

            <fieldset>
              <legend>Type</legend>
              <div className="in-types">
                <button type="button" className="as-type guidance" aria-pressed={kind === "guidance"} onClick={() => setKind("guidance")}>
                  <b>Guidance</b>
                  <span>Agents follow it and use judgement.</span>
                </button>
                <button type="button" className="as-type guardrail" aria-pressed={kind === "guardrail"} onClick={() => setKind("guardrail")}>
                  <b>Guardrail</b>
                  <span>Never crossed. Agents stop and ask you first.</span>
                </button>
              </div>
            </fieldset>

            <fieldset>
              <legend>Applies to</legend>
              <div className="in-scopes">
                <button type="button" className={cn("gv-fchip", scope === "all" && "on")} aria-pressed={scope === "all"} onClick={() => setScope("all")}>
                  <span className="rs-ddot" style={{ background: ALL_DOT }} />
                  All agents
                  <span className="c">{agentsData ? total : ""}</span>
                </button>
                {scopeDepts.map((d) => (
                  <button
                    key={d.id}
                    type="button"
                    className={cn("gv-fchip", scope === d.id && "on")}
                    aria-pressed={scope === d.id}
                    onClick={() => setScope(d.id)}
                  >
                    <DepartmentGlyph department={d.id} size={13} />
                    {d.name}
                    <span className="c">{deptCounts.get(d.id) ?? 0}</span>
                  </button>
                ))}
                <button
                  type="button"
                  className={cn("gv-fchip", scope === "agent" && "on")}
                  aria-pressed={scope === "agent"}
                  onClick={() => setScope("agent")}
                  disabled={agents.length === 0}
                >
                  One agent
                </button>
              </div>
              {scope === "agent" ? (
                <div className="in-agent-pick">
                  <label htmlFor="in-agent" className="gv-label">
                    Agent
                  </label>
                  <select id="in-agent" value={agentId} onChange={(e) => setAgentId(e.target.value)}>
                    <option value="">Choose an agent</option>
                    {agents.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name} · {a.departmentLabel}
                      </option>
                    ))}
                  </select>
                </div>
              ) : null}
            </fieldset>

            <div>
              <label htmlFor="in-text" className="gv-label">
                Instruction
              </label>
              <textarea
                id="in-text"
                rows={5}
                className="in-text"
                placeholder="For example: Always confirm with me before sending an email to a customer."
                value={content}
                onChange={(e) => setContent(e.target.value)}
              />
            </div>

            {formError ? (
              <p role="alert" className="in-error">
                {formError}
              </p>
            ) : null}

            <div className="in-form-foot">
              <div className="in-switch">
                <button
                  type="button"
                  role="switch"
                  className="gv-switch"
                  aria-checked={enabled}
                  aria-labelledby="in-switch-label"
                  onClick={() => setEnabled((v) => !v)}
                >
                  <span className="k" />
                </button>
                <span id="in-switch-label">Switch on when saved</span>
              </div>
              <button type="button" className="gv-btn dark" style={{ minHeight: 48, padding: "0 24px", fontSize: 15 }} disabled={!canSave} onClick={() => void create()}>
                {saving ? "Saving…" : kind === "guardrail" ? "Create guardrail" : "Create instruction"}
              </button>
            </div>
            <p className="in-summary" aria-live="polite">
              {summary}
            </p>
          </section>

          <aside aria-labelledby="stack-heading" className="as-dark in-stack">
            <span className="eb">How agents read them</span>
            <h2 id="stack-heading">Rules stack from broad to specific</h2>
            <ol>
              <li className="l1">
                <b>1. Guardrails</b>
                <span>Always win, at every level.</span>
              </li>
              <li className="l2">
                <b>2. Whole team guidance</b>
                <span>
                  Applies to all {agentsData ? total : ""} {total === 1 ? "agent" : "agents"}.
                </span>
              </li>
              <li className="l3">
                <b>3. Department guidance</b>
                <span>Adds detail for one team.</span>
              </li>
              <li className="l4">
                <b>4. Single agent</b>
                <span>Most specific. Wins over 2 and 3.</span>
              </li>
            </ol>
            <p>When two rules disagree, the more specific one is used, unless a guardrail says otherwise.</p>
          </aside>
        </div>

        <section aria-labelledby="tpl-heading" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="in-tpl-head">
            <h2 id="tpl-heading">Start from a template</h2>
            <p>Common rules teams add first. Using one fills in the type and who it applies to.</p>
          </div>
          <div className="in-tpls">
            {TEMPLATES.map((t) => (
              <article key={t.name} className="as-panel in-tpl">
                <div className="in-tpl-top">
                  <span className={cn("in-badge", t.kind)}>{t.kind === "guardrail" ? "Guardrail" : "Guidance"}</span>
                  <span className="in-scope">
                    {t.scope === "all" ? (
                      <span className="rs-ddot" style={{ background: ALL_DOT }} />
                    ) : (
                      <DepartmentGlyph department={t.scope} size={13} />
                    )}
                    {t.scope === "all" ? "All agents" : deptName(t.scope)}
                  </span>
                </div>
                <b>{t.name}</b>
                <p>{t.text}</p>
                <button type="button" className="gv-btn outline sm" onClick={() => applyTemplate(t)}>
                  Use template
                </button>
              </article>
            ))}
          </div>
        </section>

        <section aria-labelledby="active-heading" className="as-panel in-list">
          <div className="in-list-head">
            <h2 id="active-heading">Your instructions</h2>
            <div role="group" aria-label="Filter" className="as-filter">
              <button type="button" aria-pressed={filter === "all"} onClick={() => setFilter("all")}>
                All {counts.all}
              </button>
              <button type="button" aria-pressed={filter === "guidance"} onClick={() => setFilter("guidance")}>
                Guidance {counts.guidance}
              </button>
              <button type="button" aria-pressed={filter === "guardrail"} onClick={() => setFilter("guardrail")}>
                Guardrails {counts.guardrail}
              </button>
            </div>
          </div>
          {error ? (
            <div style={{ padding: 20 }}>
              <WorkSectionErrorCard
                title="Couldn't load instructions"
                message="Your instructions are safe. Check your connection and try again."
                error={error}
                onRetry={() => void mutate()}
              />
            </div>
          ) : (isLoading || !orgReady) && !data && !orgError ? (
            <div style={{ padding: 20, display: "grid", gap: 12 }} aria-busy="true" aria-label="Loading instructions">
              <div className="gv-skel" style={{ width: "40%" }} />
              <div className="gv-skel" style={{ width: "70%" }} />
              <div className="gv-skel" style={{ width: "55%" }} />
            </div>
          ) : instructions.length === 0 ? (
            <div className="in-empty">
              <div className="as-art">
                {/* eslint-disable-next-line @next/next/no-img-element -- static library scene */}
                <img src="/illustrations/agents-playbook.svg" alt="" />
              </div>
              <div style={{ flex: "1 1 300px" }}>
                <h3>Your playbook is empty</h3>
                <p>
                  Agents are running on their default behaviour. Add one guardrail for anything that touches customers or
                  money, then layer guidance on top.
                </p>
              </div>
            </div>
          ) : visible.length === 0 ? (
            <p className="as-copy" style={{ padding: 20 }}>
              No {filter === "guardrail" ? "guardrails" : "guidance"} yet.
            </p>
          ) : (
            <ul className="in-items">
              {visible.map((i) => {
                const k = kindOf(i)
                const s = scopeLabel(i)
                const updated = formatDate(i.updated_at || i.created_at)
                return (
                  <li key={i.id} className={cn("in-item", !i.is_active && "off")}>
                    <div className="in-item-main">
                      <div className="in-item-top">
                        <span className={cn("in-badge", k)}>{k === "guardrail" ? "Guardrail" : "Guidance"}</span>
                        <b>{i.name}</b>
                        <span className="in-scope">
                          {s.department ? (
                            <DepartmentGlyph department={s.department} size={12} />
                          ) : (
                            <span className="rs-ddot" style={{ background: ALL_DOT }} />
                          )}
                          {s.label}
                        </span>
                        {!i.is_active ? <span className="in-badge off">Off</span> : null}
                      </div>
                      <p>{i.content}</p>
                      {updated ? <span className="meta">Updated {updated}</span> : null}
                    </div>
                    <div className="in-item-actions">
                      <button
                        type="button"
                        role="switch"
                        className="gv-switch"
                        aria-checked={i.is_active}
                        aria-label={`${i.is_active ? "Switch off" : "Switch on"} ${i.name}`}
                        disabled={busyId === i.id}
                        onClick={() => void toggle(i)}
                      >
                        <span className="k" />
                      </button>
                      <button
                        type="button"
                        className="gv-btn plain sm"
                        disabled={busyId === i.id}
                        onClick={() => setDeleteTarget(i)}
                        aria-label={`Delete ${i.name}`}
                      >
                        Delete
                      </button>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </section>
      </div>

      <AlertDialog open={Boolean(deleteTarget)} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete &ldquo;{deleteTarget?.name}&rdquo;?</AlertDialogTitle>
            <AlertDialogDescription>
              Agents stop following it on their next run. To pause it instead, switch it off.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep it</AlertDialogCancel>
            <AlertDialogAction
              disabled={Boolean(busyId)}
              onClick={(e) => {
                e.preventDefault()
                if (deleteTarget) void remove(deleteTarget)
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </WsPage>
  )
}
