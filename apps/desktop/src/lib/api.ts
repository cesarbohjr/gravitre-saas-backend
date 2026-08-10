import type { DesktopSession } from "./session"

async function apiFetch(
  session: DesktopSession,
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const url = `${session.apiBase.replace(/\/$/, "")}${path.startsWith("/") ? path : `/${path}`}`
  const headers = new Headers(init.headers)
  headers.set("Authorization", `Bearer ${session.accessToken}`)
  headers.set("x-org-id", session.orgId)
  headers.set("x-environment", session.environment || "production")
  if (!headers.has("content-type") && init.body) {
    headers.set("content-type", "application/json")
  }
  return fetch(url, { ...init, headers })
}

export type ActivityEvent = {
  id?: string
  title?: string
  summary?: string
  created_at?: string
  createdAt?: string
  href?: string
  source?: string
}

export type ApprovalItem = {
  id?: string
  run_id?: string
  runId?: string
  title?: string
  summary?: string
  status?: string
  created_at?: string
}

export async function fetchActivity(session: DesktopSession, limit = 8): Promise<ActivityEvent[]> {
  const res = await apiFetch(session, `/api/activity/recent?limit=${limit}`)
  if (!res.ok) throw new Error(`Activity failed (${res.status})`)
  const data = (await res.json()) as { events?: ActivityEvent[] }
  return data.events ?? []
}

export async function fetchApprovals(session: DesktopSession): Promise<ApprovalItem[]> {
  const res = await apiFetch(session, "/api/approvals")
  if (!res.ok) throw new Error(`Approvals failed (${res.status})`)
  const data = (await res.json()) as { approvals?: ApprovalItem[]; items?: ApprovalItem[] }
  return data.approvals ?? data.items ?? []
}

export async function decideApproval(
  session: DesktopSession,
  runId: string,
  decision: "approve" | "reject",
): Promise<void> {
  const res = await apiFetch(session, `/api/approvals/${runId}/${decision}`, {
    method: "POST",
    body: JSON.stringify({}),
  })
  if (!res.ok) throw new Error(`${decision} failed (${res.status})`)
}

export async function sendChat(
  session: DesktopSession,
  message: string,
  spokenMode: boolean,
): Promise<string> {
  const res = await apiFetch(session, "/api/assistant/chat", {
    method: "POST",
    body: JSON.stringify({
      message,
      spoken_mode: spokenMode,
      surface: spokenMode ? "voice" : "desktop_chat",
    }),
  })
  if (!res.ok) {
    const detail = await res.text().catch(() => "")
    throw new Error(detail || `Chat failed (${res.status})`)
  }
  const data = (await res.json().catch(() => ({}))) as {
    reply?: string
    message?: string
    content?: string
    text?: string
  }
  return data.reply || data.message || data.content || data.text || "Done."
}

export async function openDeepLink(path: string) {
  try {
    const { invoke } = await import("@tauri-apps/api/core")
    await invoke("open_web_deep_link", { path })
  } catch {
    const base = "https://gravitre.app"
    window.open(`${base}${path.startsWith("/") ? path : `/${path}`}`, "_blank", "noopener,noreferrer")
  }
}
