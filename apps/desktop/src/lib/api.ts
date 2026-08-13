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

export type DesktopChatTurn = {
  role: "user" | "assistant"
  text: string
}

function parseSseEvent(dataLine: string): { type?: string; delta?: string } | null {
  if (!dataLine || dataLine === "[DONE]") return null
  try {
    const parsed = JSON.parse(dataLine) as { type?: string; delta?: string }
    return parsed
  } catch {
    return null
  }
}

async function readAssistantSseText(res: Response): Promise<string> {
  if (!res.body) return ""
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  let assembled = ""

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    buffer = buffer.replace(/\r\n/g, "\n")
    let splitAt = buffer.indexOf("\n\n")
    while (splitAt >= 0) {
      const rawBlock = buffer.slice(0, splitAt)
      buffer = buffer.slice(splitAt + 2)
      const dataLine = rawBlock
        .split("\n")
        .find((line) => line.startsWith("data:"))
        ?.slice(5)
        .trim()
      const event = parseSseEvent(dataLine || "")
      if (event?.type === "text-delta" && event.delta) {
        assembled += event.delta
      }
      splitAt = buffer.indexOf("\n\n")
    }
  }
  const finalLine = buffer
    .split("\n")
    .find((line) => line.startsWith("data:"))
    ?.slice(5)
    .trim()
  const tail = parseSseEvent(finalLine || "")
  if (tail?.type === "text-delta" && tail.delta) {
    assembled += tail.delta
  }
  return assembled.trim()
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
  history: DesktopChatTurn[] = [],
): Promise<string> {
  const messages = [
    ...history
      .slice(-40)
      .map((turn) => ({
        role: turn.role,
        parts: [{ type: "text", text: turn.text }],
      }))
      .filter((turn) => turn.parts[0].text.trim()),
    { role: "user", parts: [{ type: "text", text: message }] },
  ]
  const res = await apiFetch(session, "/api/assistant/chat", {
    method: "POST",
    body: JSON.stringify({
      messages,
      spoken_mode: spokenMode,
      surface: spokenMode ? "voice" : "desktop_chat",
    }),
  })
  if (!res.ok) {
    const detail = await res.text().catch(() => "")
    throw new Error(detail || `Chat failed (${res.status})`)
  }
  const contentType = res.headers.get("content-type") || ""
  if (contentType.includes("text/event-stream")) {
    const streamed = await readAssistantSseText(res)
    if (streamed) return streamed
    return "Done."
  }
  const data = (await res.json().catch(() => ({}))) as {
    reply?: string
    message?: string
    content?: string
    text?: string
  }
  return data.reply || data.message || data.content || data.text || "Done."
}

export type DesktopVoiceStatus = {
  enabled: boolean
  blocked: boolean
  reason?: string
}

export async function fetchVoiceStatus(session: DesktopSession): Promise<DesktopVoiceStatus> {
  const res = await apiFetch(session, "/api/voice/status")
  if (!res.ok) {
    if (res.status === 403) {
      return {
        enabled: false,
        blocked: true,
        reason: "Voice is turned off for this organization or unavailable for your seat.",
      }
    }
    return {
      enabled: false,
      blocked: false,
      reason: `Voice status failed (${res.status})`,
    }
  }
  const payload = (await res.json().catch(() => ({}))) as {
    tts_enabled?: boolean
  }
  const enabled = Boolean(payload.tts_enabled)
  return {
    enabled,
    blocked: false,
    reason: enabled ? undefined : "Voice output is not configured for this workspace.",
  }
}

export async function synthesizeVoiceReply(
  session: DesktopSession,
  text: string,
): Promise<Blob> {
  const res = await apiFetch(session, "/api/voice/tts", {
    method: "POST",
    headers: { Accept: "audio/mpeg" },
    body: JSON.stringify({
      text,
    }),
  })
  if (!res.ok) {
    const detail = await res.text().catch(() => "")
    throw new Error(detail || `Voice synthesis failed (${res.status})`)
  }
  return await res.blob()
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
