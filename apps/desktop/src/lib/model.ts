/**
 * View models for the desktop screens. Everything is read from what the API
 * returned; a value the backend did not send stays out of the UI.
 */
import { humanizeToolName } from "./tools"
import type { ActivityEvent, AgentJob } from "./api"

export type Status = "running" | "waiting" | "done" | "failed" | "paused" | "queued"

export const STATUS: Record<Status, { cls: string; label: string }> = {
  running: { cls: "st-run", label: "Running" },
  waiting: { cls: "st-wait", label: "Needs approval" },
  done: { cls: "st-done", label: "Done" },
  failed: { cls: "st-fail", label: "Failed" },
  paused: { cls: "st-q", label: "Paused" },
  queued: { cls: "st-q", label: "Queued" },
}

export type StepState = "done" | "running" | "waiting" | "queued" | "failed"

const AVATAR_COLORS = ["#5b5bd6", "#2b59e0", "#0b8a5c", "#c0533a", "#8a5a06", "#4a6a8e", "#2f7d6d", "#9a4fb5"]

export function avatarColor(seed: string): string {
  let h = 0
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0
  return AVATAR_COLORS[h % AVATAR_COLORS.length]
}

export function initials(name: string): string {
  const words = name.replace(/[^\p{L}\p{N} ]/gu, " ").trim().split(/\s+/).filter(Boolean)
  if (!words.length) return "G"
  if (words.length === 1) return words[0].slice(0, 1).toUpperCase()
  return (words[0][0] + words[words.length - 1][0]).toUpperCase()
}

/** Two-letter badge for an integration slug: hubspot → HS, google_sheets → GS. */
export function systemBadge(slug: string | null | undefined): string {
  const s = (slug || "").trim()
  if (!s) return ""
  const known: Record<string, string> = {
    hubspot: "HS",
    salesforce: "SF",
    slack: "SL",
    gmail: "GM",
    google: "G",
    linear: "LN",
    notion: "NO",
    jira: "JI",
    confluence: "CF",
    zendesk: "ZD",
    stripe: "ST",
    apollo: "AP",
  }
  const key = s.toLowerCase().split(/[._\s-]/)[0]
  if (known[key]) return known[key]
  const parts = s.split(/[._\s-]+/).filter(Boolean)
  return (parts.length > 1 ? parts[0][0] + parts[1][0] : s.slice(0, 2)).toUpperCase()
}

export function timeAgo(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return ""
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return ""
  const mins = Math.floor((now - t) / 60000)
  if (mins < 1) return "now"
  if (mins < 60) return `${mins}m`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d`
  return new Date(t).toLocaleDateString(undefined, { month: "short", day: "numeric" })
}

export function clock(iso: string | null | undefined): string {
  if (!iso) return ""
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })
}

export function dayLabel(iso: string | null | undefined, now = new Date()): string {
  if (!iso) return "Earlier"
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return "Earlier"
  const start = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime()
  const diff = Math.round((start(now) - start(d)) / 86400000)
  if (diff === 0) return "Today"
  if (diff === 1) return "Yesterday"
  return d.toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })
}

/* ------------------------------------------------------------------ */
/* Assignments (agent jobs)                                             */
/* ------------------------------------------------------------------ */

export type AssignmentStep = { title: string; detail: string; system: string; state: StepState }

export type Assignment = {
  id: string
  title: string
  objective: string
  agent: string
  agentId: string | null
  status: Status
  /** 0-100 when reported or finished; null when the run did not report progress. */
  progress: number | null
  createdAt: string
  finishedAt: string | null
  steps: AssignmentStep[]
  outcome: string | null
  approvalPrompt: string | null
}

const READABLE_KEYS = ["objective", "title", "goal", "task", "description", "prompt", "message", "summary", "query"]

function readable(node: unknown): string | null {
  if (typeof node === "string") {
    const text = node.trim()
    if (!text) return null
    const at = text.search(/[[{]/)
    if (at >= 0) {
      try {
        const found = readable(JSON.parse(text.slice(at)))
        if (found) return found
      } catch {
        /* plain text */
      }
    }
    return text
  }
  if (Array.isArray(node)) {
    for (const entry of node) {
      const found = readable(entry)
      if (found) return found
    }
    return null
  }
  if (node && typeof node === "object") {
    const rec = node as Record<string, unknown>
    for (const key of READABLE_KEYS) {
      const found = readable(rec[key])
      if (found) return found
    }
  }
  return null
}

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : ""
}

function statusOf(job: AgentJob): Status {
  const r = job.result || {}
  switch (job.status) {
    case "queued":
      return "queued"
    case "running":
      return "running"
    case "paused":
      return "paused"
    case "failed":
    case "cancelled":
      return "failed"
    case "completed":
      return r.requires_approval || r.needs_human_input ? "waiting" : "done"
    default:
      return "queued"
  }
}

export function toAssignment(job: AgentJob): Assignment {
  const r = (job.result || {}) as Record<string, unknown>
  const task = (r.task && typeof r.task === "object" ? r.task : {}) as Record<string, unknown>
  const objective =
    readable(text(task.description)) || readable(text(r.finding_description)) || readable(text(r.summary)) || "Agent task"
  const title = (readable(text(r.action_title)) || objective).slice(0, 96)
  const status = statusOf(job)
  const pct = typeof r.progress_percent === "number" ? Math.round(r.progress_percent <= 1 ? r.progress_percent * 100 : r.progress_percent) : null
  const calls = Array.isArray(r.tool_calls) ? r.tool_calls : []
  const steps: AssignmentStep[] = calls.flatMap((entry) => {
    if (!entry || typeof entry !== "object") return []
    const row = entry as Record<string, unknown>
    const res = (row.result && typeof row.result === "object" ? row.result : {}) as Record<string, unknown>
    const tool = text(res.action) || text(row.action) || text(row.tool) || "tool"
    const ok = res.success === true
    const err = text(res.error) || text(res.error_detail)
    return [
      {
        title: humanizeToolName(tool),
        detail: ok ? "Done" : err || "Didn't complete",
        system: systemBadge(tool.split(/[._:]/)[0]),
        state: ok ? "done" : "failed",
      },
    ]
  })
  if (status === "running") steps.push({ title: "Working", detail: "In progress", system: "", state: "running" })
  if (status === "waiting") {
    steps.push({ title: "Your approval", detail: text(r.human_input_prompt) || "Waiting on a decision", system: "", state: "waiting" })
  }
  if (!steps.length) {
    const runState: StepState = status === "done" ? "done" : status === "failed" ? "failed" : "queued"
    steps.push({ title: "Run the task", detail: status === "queued" ? "Queued" : STATUS[status].label, system: "", state: runState })
  }
  const summary = readable(text(r.summary)) || readable(text(r.answer))
  const error = text(job.error) || text(r.error)
  let outcome: string | null = null
  if (status === "done") outcome = summary && summary !== title && summary !== objective ? summary : "Finished."
  else if (status === "failed") outcome = error || "The run stopped before it finished."
  return {
    id: job.jobId,
    title,
    objective,
    agent: text(r.agent_name) || "Gravitre",
    agentId: text(r.agent_id) || null,
    status,
    progress: status === "done" || status === "waiting" ? 100 : pct,
    createdAt: job.createdAt,
    finishedAt: job.finishedAt,
    steps,
    outcome,
    approvalPrompt: text(r.human_input_prompt) || null,
  }
}

/* ------------------------------------------------------------------ */
/* Activity                                                             */
/* ------------------------------------------------------------------ */

export type ActivityTone = "run" | "wait" | "done" | "fail" | "q"

export function activityStatus(e: ActivityEvent): { cls: string; label: string } {
  const s = (e.status || "").toLowerCase()
  if (["success", "succeeded", "completed", "done", "approved", "ok", "sent", "created", "updated"].includes(s)) {
    return { cls: "st-done", label: s === "approved" ? "Approved" : "Done" }
  }
  if (["failed", "error", "rejected", "cancelled", "blocked"].includes(s)) {
    return { cls: "st-fail", label: s === "rejected" ? "Rejected" : s === "cancelled" ? "Cancelled" : "Failed" }
  }
  if (["pending", "waiting", "pending_approval", "awaiting_approval"].includes(s)) return { cls: "st-wait", label: "Waiting" }
  if (["running", "in_progress", "started"].includes(s)) return { cls: "st-run", label: "Running" }
  const label = s ? s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, " ") : (e.source || "Event").replace(/_/g, " ")
  return { cls: "st-q", label: label.charAt(0).toUpperCase() + label.slice(1) }
}

export function activityActor(e: ActivityEvent): string {
  const m = e.metadata || {}
  return (
    text(m.agent_name) ||
    text(m.actor_name) ||
    text(m.user_name) ||
    text(m.requested_by) ||
    (e.source ? e.source.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()) : "Gravitre")
  )
}

/** "Step 4 of 4 · waiting on approval", "6 of 14 done", "43%": only what the run reported. */
export function progressLine(a: Assignment): string {
  const total = a.steps.length
  const done = a.steps.filter((s) => s.state === "done").length
  const step = total > 1 ? `Step ${Math.min(done + 1, total)} of ${total}` : ""
  if (a.status === "waiting") return [step, "waiting on approval"].filter(Boolean).join(" · ")
  if (a.status === "running") return step || (a.progress != null ? `${a.progress}%` : "Running")
  if (a.status === "queued") return "Queued"
  if (a.status === "paused") return "Paused"
  return STATUS[a.status].label
}

export function greeting(name: string | undefined, now = new Date()): string {
  const h = now.getHours()
  const part = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening"
  const first = (name || "").split(" ")[0]
  return first ? `${part}, ${first}` : part
}

/** "2 min", "1 h", "Yesterday": the age column in lists. */
export function age(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return ""
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return ""
  const mins = Math.floor((now - t) / 60000)
  if (mins < 1) return "now"
  if (mins < 60) return `${mins} min`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} h`
  if (hours < 48) return "Yesterday"
  return new Date(t).toLocaleDateString(undefined, { month: "short", day: "numeric" })
}

/** Clock time today, otherwise the weekday or date: list timestamps. */
export function stamp(iso: string | null | undefined, now = new Date()): string {
  if (!iso) return ""
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ""
  if (d.toDateString() === now.toDateString()) return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hour12: false })
  const days = (now.getTime() - d.getTime()) / 86400000
  if (days < 7) return d.toLocaleDateString(undefined, { weekday: "short" })
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" })
}

/** Bar width: finished steps out of the plan when there is one, else what the run reported. */
export function percentDone(a: Assignment): number | null {
  const total = a.steps.length
  if (total > 1) return Math.round((a.steps.filter((s) => s.state === "done").length / total) * 100)
  return a.progress
}
