import { normalizeApprovals, type Approval } from "@web/components/approvals/decision-queue/model"
import { parseContextSources, type ContextSourcesSummary } from "@web/lib/context-sources"
import type { DesktopSession } from "./session"

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

/** Thrown when the session can't be renewed; the app returns to sign-in. */
export class SignedOutError extends ApiError {}

type SessionStore = {
  get: () => DesktopSession | null
  set: (session: DesktopSession | null) => void
}

async function detailOf(res: Response, fallback: string): Promise<string> {
  const body = (await res.json().catch(() => null)) as { detail?: unknown; message?: unknown } | null
  const detail = body?.detail ?? body?.message
  if (typeof detail === "string" && detail.trim()) return detail
  if (Array.isArray(detail) && detail.length) return fallback
  return fallback
}

export type Me = {
  userId: string
  email: string
  name: string
  role: string | null
  orgId: string | null
  organizations: { id: string; name: string; role: string | null }[]
}

export type Surface = "web" | "desktop" | "extension" | "voice"

export type Conversation = {
  id: string
  title: string
  preview: string | null
  updatedAt: string
  createdAt: string
  messageCount: number
  /** Where the conversation was started; null for conversations from before this was recorded. */
  surface: Surface | null
}

export type StoredMessage = { id: string; role: "user" | "assistant"; content: string; createdAt: string }

export type AgentJob = {
  jobId: string
  kind: string
  status: string
  result: Record<string, unknown> | null
  error: string | null
  createdAt: string
  finishedAt: string | null
}

export type ActivityEvent = {
  id: string
  source: string | null
  event_type: string | null
  title: string | null
  body: string | null
  status: string | null
  entity_type: string | null
  entity_id: string | null
  url: string | null
  integration: string | null
  metadata: Record<string, unknown> | null
  created_at: string | null
}

export type Agent = { id: string; name: string; role: string | null; status: string | null; department: string | null }

export type PendingTask = {
  title: string
  status: string
  steps: string[]
}

export type ChatEvents = {
  onText?: (text: string) => void
  onStatus?: (status: string) => void
}

export type ChatResult = {
  text: string
  sources: ContextSourcesSummary | null
  pendingTask: PendingTask | null
}

export type ChatTurn = { role: "user" | "assistant"; text: string }

function str(value: unknown): string {
  return typeof value === "string" ? value.trim() : ""
}

function surfaceOf(value: unknown): Surface | null {
  const s = str(value).toLowerCase()
  return s === "web" || s === "desktop" || s === "extension" || s === "voice" ? s : null
}

function toConversation(c: Record<string, unknown>, fallbackTitle = "New conversation"): Conversation {
  return {
    id: str(c.id),
    title: str(c.title) || fallbackTitle,
    preview: str(c.preview) || null,
    updatedAt: str(c.updated_at) || str(c.created_at),
    createdAt: str(c.created_at) || str(c.updated_at),
    messageCount: Number(c.message_count) || 0,
    surface: surfaceOf(c.surface),
  }
}

function pendingTaskOf(value: unknown): PendingTask | null {
  if (!value || typeof value !== "object") return null
  const row = value as Record<string, unknown>
  const status = str(row.status).toLowerCase()
  if (status && !["pending", "pending_approval", "awaiting_approval", "awaiting_confirmation", "staged"].includes(status)) {
    return null
  }
  const params = (row.params && typeof row.params === "object" ? row.params : {}) as Record<string, unknown>
  const steps = Array.isArray(params.steps)
    ? params.steps
        .map((step) => {
          if (typeof step === "string") return step.trim()
          if (step && typeof step === "object") {
            const s = step as Record<string, unknown>
            return str(s.description) || str(s.title) || str(s.text) || str(s.action)
          }
          return ""
        })
        .filter(Boolean)
    : []
  const title = str(row.title) || str(row.summary) || str(row.description) || str(params.title) || "Action waiting for approval"
  return { title, status: status || "pending", steps }
}

/** Reads the assistant's AI SDK stream: text deltas plus the data-intelligence record. */
async function readChatStream(res: Response, events: ChatEvents): Promise<ChatResult> {
  const out: ChatResult = { text: "", sources: null, pendingTask: null }
  if (!res.body) return out
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  const handle = (block: string) => {
    const data = block
      .split("\n")
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trim())
      .join("")
    if (!data || data === "[DONE]") return
    let event: Record<string, unknown>
    try {
      event = JSON.parse(data) as Record<string, unknown>
    } catch {
      return
    }
    if (event.type === "text-delta" && typeof event.delta === "string") {
      out.text += event.delta
      events.onText?.(out.text)
    } else if (event.type === "data-intelligence" && event.data && typeof event.data === "object") {
      const intel = event.data as Record<string, unknown>
      const sources = parseContextSources(intel.contextSources)
      if (sources) out.sources = sources
      const pending = pendingTaskOf(intel.pendingTask)
      if (pending) out.pendingTask = pending
      const status = str(intel.answerExplanation)
      if (status) events.onStatus?.(status)
    } else if (event.type === "error") {
      const message = str(event.errorText) || str(event.error) || "The answer stopped early."
      throw new ApiError(message, 500)
    }
  }
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n")
    let split = buffer.indexOf("\n\n")
    while (split >= 0) {
      handle(buffer.slice(0, split))
      buffer = buffer.slice(split + 2)
      split = buffer.indexOf("\n\n")
    }
  }
  if (buffer.trim()) handle(buffer)
  out.text = out.text.trim()
  return out
}

export function createApi(store: SessionStore) {
  let refreshing: Promise<DesktopSession> | null = null

  const refresh = (session: DesktopSession): Promise<DesktopSession> => {
    if (!session.refreshToken) {
      store.set(null)
      return Promise.reject(new SignedOutError("Your desktop session ended. Sign in again.", 401))
    }
    refreshing ??= (async () => {
      try {
        const res = await fetch(`${session.apiBase}/api/auth/companion-refresh`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ refresh_token: session.refreshToken }),
        })
        if (res.status === 401) {
          store.set(null)
          throw new SignedOutError("Your desktop session ended. Sign in again.", 401)
        }
        if (!res.ok) throw new ApiError(await detailOf(res, "Couldn't reach Gravitre"), res.status)
        const body = (await res.json()) as { access_token: string; refresh_token: string; expires_at?: number }
        const next: DesktopSession = {
          ...session,
          accessToken: body.access_token,
          refreshToken: body.refresh_token,
          expiresAt: typeof body.expires_at === "number" ? body.expires_at : null,
        }
        store.set(next)
        return next
      } finally {
        refreshing = null
      }
    })()
    return refreshing
  }

  const current = async (): Promise<DesktopSession> => {
    const session = store.get()
    if (!session) throw new SignedOutError("Signed out", 401)
    const soon = session.expiresAt != null && session.expiresAt * 1000 - Date.now() < 90_000
    return soon && session.refreshToken ? refresh(session) : session
  }

  const send = (session: DesktopSession, path: string, init: RequestInit) => {
    const headers = new Headers(init.headers)
    headers.set("Authorization", `Bearer ${session.accessToken}`)
    headers.set("x-org-id", session.orgId)
    headers.set("x-environment", session.environment || "production")
    if (init.body && !(init.body instanceof FormData) && !headers.has("content-type")) {
      headers.set("content-type", "application/json")
    }
    return fetch(`${session.apiBase}${path}`, { ...init, headers })
  }

  const request = async (path: string, init: RequestInit = {}): Promise<Response> => {
    let session = await current()
    let res = await send(session, path, init)
    if (res.status === 401) {
      session = await refresh(session)
      res = await send(session, path, init)
      if (res.status === 401) {
        store.set(null)
        throw new SignedOutError("Your desktop session ended. Sign in again.", 401)
      }
    }
    return res
  }

  const json = async <T>(path: string, init: RequestInit = {}, fallback = "Request failed"): Promise<T> => {
    const res = await request(path, init)
    if (!res.ok) throw new ApiError(await detailOf(res, `${fallback} (${res.status})`), res.status)
    return (await res.json()) as T
  }

  const post = <T>(path: string, body: unknown = {}, fallback?: string) =>
    json<T>(path, { method: "POST", body: JSON.stringify(body) }, fallback)

  return {
    async me(): Promise<Me> {
      const body = await json<Record<string, unknown>>("/api/auth/me", {}, "Couldn't load your account")
      const user = (body.user || {}) as Record<string, unknown>
      const email = str(body.email) || str(user.email)
      const orgs = Array.isArray(body.organizations) ? (body.organizations as Record<string, unknown>[]) : []
      return {
        userId: str(body.user_id),
        email,
        name: str(user.full_name) || str(user.display_name) || email.split("@")[0] || "You",
        role: str(body.role) || null,
        orgId: str(body.org_id) || null,
        organizations: orgs
          .map((o) => ({ id: str(o.id), name: str(o.name) || "Workspace", role: str(o.role) || null }))
          .filter((o) => o.id),
      }
    },

    async conversations(search = ""): Promise<Conversation[]> {
      const q = new URLSearchParams({ limit: "60" })
      if (search.trim()) q.set("search", search.trim())
      const body = await json<{ conversations?: Record<string, unknown>[] }>(`/api/conversations?${q}`, {}, "Couldn't load conversations")
      return (body.conversations || []).map((c) => toConversation(c))
    },

    async createConversation(title: string, surface: Surface = "desktop"): Promise<Conversation> {
      const c = await post<Record<string, unknown>>(
        "/api/conversations",
        { title: title.slice(0, 80), surface },
        "Couldn't start a conversation",
      )
      return { ...toConversation(c, title), surface: surfaceOf(c.surface) ?? surface }
    },

    async messages(conversationId: string): Promise<StoredMessage[]> {
      const body = await json<{ messages?: Record<string, unknown>[] }>(
        `/api/conversations/${encodeURIComponent(conversationId)}/messages?limit=80`,
        {},
        "Couldn't load the conversation",
      )
      return (body.messages || [])
        .filter((m) => m.role === "user" || m.role === "assistant")
        .map((m) => ({
          id: str(m.id),
          role: m.role as "user" | "assistant",
          content: typeof m.content === "string" ? m.content : "",
          createdAt: str(m.created_at),
        }))
    },

    async chat(
      args: { history: ChatTurn[]; message: string; conversationId: string | null; agentId: string | null; spoken?: boolean },
      events: ChatEvents = {},
      signal?: AbortSignal,
    ): Promise<ChatResult> {
      const messages = [...args.history.slice(-30), { role: "user" as const, text: args.message }]
        .filter((turn) => turn.text.trim())
        .map((turn, i) => ({ id: `d${i}`, role: turn.role, parts: [{ type: "text", text: turn.text }] }))
      const res = await request("/api/assistant/chat", {
        method: "POST",
        signal,
        headers: { Accept: "text/event-stream" },
        body: JSON.stringify({
          messages,
          conversation_id: args.conversationId,
          agent_id: args.agentId,
          spoken_mode: Boolean(args.spoken),
          surface: args.spoken ? "voice" : "desktop",
        }),
      })
      if (!res.ok) throw new ApiError(await detailOf(res, `The answer didn't come through (${res.status})`), res.status)
      if ((res.headers.get("content-type") || "").includes("text/event-stream")) return readChatStream(res, events)
      const body = (await res.json().catch(() => ({}))) as Record<string, unknown>
      const text = str(body.reply) || str(body.message) || str(body.content) || str(body.text)
      events.onText?.(text)
      return { text, sources: null, pendingTask: null }
    },

    async agents(): Promise<Agent[]> {
      const body = await json<{ agents?: Record<string, unknown>[] } | Record<string, unknown>[]>("/api/agents", {}, "Couldn't load agents")
      const rows = Array.isArray(body) ? body : body.agents || []
      return rows
        .map((a) => {
          const config = (a.config && typeof a.config === "object" ? a.config : {}) as Record<string, unknown>
          return {
            id: str(a.id),
            name: str(a.name) || "Agent",
            role: str(a.role) || null,
            status: str(a.status) || null,
            department: str(a.department) || str(config.department) || null,
          }
        })
        .filter((a) => a.id)
    },

    /** What the signed-in role may do in this workspace (approve_writes and so on). */
    async capabilities(): Promise<{ role: string | null; capabilities: string[] } | null> {
      try {
        const body = await json<{ my_role?: string | null; my_capabilities?: unknown }>("/api/org/role-permissions")
        const caps = Array.isArray(body.my_capabilities) ? body.my_capabilities.map(String) : null
        return caps ? { role: str(body.my_role) || null, capabilities: caps } : null
      } catch (err) {
        if (err instanceof SignedOutError) throw err
        return null
      }
    },

    async approvals(): Promise<Approval[]> {
      return normalizeApprovals(await json<unknown>("/api/approvals", {}, "Couldn't load approvals"))
    },

    async approvalHistory(): Promise<Approval[]> {
      return normalizeApprovals(await json<unknown>("/api/approvals?status=history", {}, "Couldn't load past decisions"))
    },

    async approve(id: string): Promise<Record<string, unknown>> {
      return post(`/api/approvals/${encodeURIComponent(id)}/approve`, {}, "Couldn't approve")
    },

    async reject(id: string, comment: string): Promise<void> {
      await post(`/api/approvals/${encodeURIComponent(id)}/reject`, { comment: comment || null }, "Couldn't reject")
    },

    async jobs(): Promise<AgentJob[]> {
      const body = await json<{ jobs?: AgentJob[] }>("/api/agent-jobs?limit=50", {}, "Couldn't load assignments")
      return body.jobs || []
    },

    async pauseJob(id: string): Promise<void> {
      await post(`/api/agent-jobs/${encodeURIComponent(id)}/pause`, {}, "Couldn't pause")
    },

    async approveJob(id: string): Promise<void> {
      await post(`/api/agent-jobs/${encodeURIComponent(id)}/approve`, {}, "Couldn't approve")
    },

    async rejectJob(id: string, reason: string): Promise<void> {
      await post(`/api/agent-jobs/${encodeURIComponent(id)}/reject`, { reason: reason || null }, "Couldn't reject")
    },

    async activity(limit = 50): Promise<ActivityEvent[]> {
      const body = await json<{ events?: ActivityEvent[] }>(`/api/activity/recent?limit=${limit}`, {}, "Couldn't load activity")
      return body.events || []
    },

    async weekTotals(): Promise<{ hoursSaved: number | null; completed: number | null }> {
      const tz = -new Date().getTimezoneOffset()
      const body = await json<{ totals?: Record<string, unknown> }>(`/api/metrics/home-reports?range=7d&tz=${tz}`, {}, "Couldn't load results")
      const num = (v: unknown) => (typeof v === "number" && Number.isFinite(v) ? v : null)
      return { hoursSaved: num(body.totals?.hoursSaved), completed: num(body.totals?.completed) }
    },

    async voiceStatus(): Promise<{ enabled: boolean; reason: string | null }> {
      const res = await request("/api/voice/status")
      if (res.status === 403) return { enabled: false, reason: "Voice is turned off for this workspace or your seat." }
      if (!res.ok) return { enabled: false, reason: "Voice isn't reachable right now." }
      const body = (await res.json().catch(() => ({}))) as { tts_enabled?: boolean; stt_enabled?: boolean }
      const enabled = body.tts_enabled !== false && body.stt_enabled !== false
      return { enabled, reason: enabled ? null : "Voice isn't set up for this workspace yet." }
    },

    async transcribe(audio: Blob, conversationId: string | null): Promise<string> {
      const form = new FormData()
      const ext = audio.type.includes("mp4") ? "m4a" : audio.type.includes("ogg") ? "ogg" : "webm"
      form.append("file", audio, `speech.${ext}`)
      const q = conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : ""
      const body = await json<{ transcript?: string }>(`/api/voice/stt${q}`, { method: "POST", body: form }, "Couldn't hear that")
      return str(body.transcript)
    },

    async speak(text: string): Promise<Blob> {
      const res = await request("/api/voice/tts", {
        method: "POST",
        headers: { Accept: "audio/mpeg" },
        body: JSON.stringify({ text }),
      })
      if (!res.ok) throw new ApiError(await detailOf(res, "Couldn't play the answer"), res.status)
      return res.blob()
    },
  }
}

export type Api = ReturnType<typeof createApi>

/** Opens a gravitre.app page (or any https URL) in the default browser. */
export async function openWeb(appBase: string, path = "/") {
  const url = /^https?:\/\//.test(path) ? path : `${appBase.replace(/\/$/, "")}/${path.replace(/^\//, "")}`
  try {
    const { invoke } = await import("@tauri-apps/api/core")
    await invoke("open_web_deep_link", { path: url })
  } catch {
    window.open(url, "_blank", "noopener,noreferrer")
  }
}

export type DesktopRelease = {
  version: string
  /** Release notes page. */
  notes: string | null
  /** Oldest version that may keep running; older builds must update. */
  minimum: string | null
}

const RELEASE_FEED = "https://gravitre.app/desktop/latest.json"

/** The published desktop release, from the same file the /download page reads. */
export async function desktopRelease(): Promise<DesktopRelease | null> {
  try {
    const res = await fetch(RELEASE_FEED, { cache: "no-store" })
    if (!res.ok) return null
    const body = (await res.json()) as { version?: unknown; releaseUrl?: unknown; minimumSupported?: unknown }
    const version = str(body.version)
    if (!version) return null
    return { version, notes: str(body.releaseUrl) || null, minimum: str(body.minimumSupported) || null }
  } catch {
    return null
  }
}

export function isNewer(latest: string, current: string): boolean {
  const a = latest.split(".").map((n) => Number.parseInt(n, 10) || 0)
  const b = current.split(".").map((n) => Number.parseInt(n, 10) || 0)
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    if ((a[i] ?? 0) !== (b[i] ?? 0)) return (a[i] ?? 0) > (b[i] ?? 0)
  }
  return false
}
