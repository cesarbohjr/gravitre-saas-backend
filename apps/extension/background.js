/** Gravitre extension service worker — API calls + auth storage. */

const DEFAULT_API =
  "https://gravitre-saas-backend-production.up.railway.app"
const DEFAULT_APP = "https://gravitre.app"

async function getSettings() {
  const data = await chrome.storage.local.get([
    "accessToken",
    "refreshToken",
    "expiresAt",
    "orgId",
    "environment",
    "apiBase",
    "appBase",
  ])
  return {
    accessToken: data.accessToken || "",
    refreshToken: data.refreshToken || "",
    expiresAt: typeof data.expiresAt === "number" ? data.expiresAt : null,
    orgId: data.orgId || "",
    environment: data.environment || "production",
    apiBase: (data.apiBase || DEFAULT_API).replace(/\/+$/, ""),
    appBase: (data.appBase || DEFAULT_APP).replace(/\/+$/, ""),
  }
}

function notSignedIn(message = "Not signed in. Open the extension and connect Gravitre.") {
  const err = new Error(message)
  err.code = "not_authenticated"
  return err
}

let refreshing = null

/**
 * The extension owns its own session (minted by /extension/connect), so it can
 * renew it here without touching the web app's session.
 */
async function refreshSession(cfg) {
  if (!cfg.refreshToken) {
    await chrome.storage.local.remove(["accessToken", "refreshToken", "expiresAt"])
    throw notSignedIn("Your Gravitre session ended. Connect again.")
  }
  refreshing ??= (async () => {
    try {
      const res = await fetch(`${cfg.apiBase}/api/auth/companion-refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: cfg.refreshToken }),
      })
      if (res.status === 401) {
        await chrome.storage.local.remove(["accessToken", "refreshToken", "expiresAt"])
        throw notSignedIn("Your Gravitre session ended. Connect again.")
      }
      if (!res.ok) throw new Error(`Couldn't reach Gravitre (${res.status})`)
      const body = await res.json()
      await chrome.storage.local.set({
        accessToken: body.access_token,
        refreshToken: body.refresh_token,
        expiresAt: typeof body.expires_at === "number" ? body.expires_at : null,
      })
      return { ...cfg, accessToken: body.access_token, refreshToken: body.refresh_token }
    } finally {
      refreshing = null
    }
  })()
  return refreshing
}

/** Authenticated request with renewal before expiry and one retry after a 401. */
async function authedFetch(path, init = {}) {
  let cfg = await getSettings()
  if (!cfg.accessToken || !cfg.orgId) throw notSignedIn()
  if (cfg.refreshToken && cfg.expiresAt && cfg.expiresAt * 1000 - Date.now() < 90_000) {
    cfg = await refreshSession(cfg)
  }
  const send = (c) =>
    fetch(`${c.apiBase}${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${c.accessToken}`,
        "Content-Type": "application/json",
        "X-Org-Id": c.orgId,
        "X-Environment": c.environment,
        ...(init.headers || {}),
      },
    })
  let res = await send(cfg)
  if (res.status === 401) {
    cfg = await refreshSession(cfg)
    res = await send(cfg)
    if (res.status === 401) {
      await chrome.storage.local.remove(["accessToken", "refreshToken", "expiresAt"])
      throw notSignedIn("Your Gravitre session ended. Connect again.")
    }
  }
  return res
}

async function apiFetch(path, { method = "GET", body } = {}) {
  const res = await authedFetch(path, {
    method,
    body: body ? JSON.stringify(body) : undefined,
  })
  const text = await res.text()
  let json = null
  try {
    json = text ? JSON.parse(text) : null
  } catch {
    json = { detail: text }
  }
  if (!res.ok) {
    const err = new Error(
      (json && typeof json.detail === "string" && json.detail) ||
        (json && json.message) ||
        `HTTP ${res.status}`,
    )
    err.status = res.status
    err.body = json
    throw err
  }
  return json
}

/** The action badge shows how many approvals are waiting. */
async function refreshBadge() {
  try {
    const cfg = await getSettings()
    if (!cfg.accessToken) {
      await chrome.action.setBadgeText({ text: "" })
      return null
    }
    const data = await apiFetch("/api/approvals")
    const n = Array.isArray(data?.approvals) ? data.approvals.length : 0
    await chrome.action.setBadgeBackgroundColor({ color: "#e2a33a" })
    await chrome.action.setBadgeText({ text: n ? String(Math.min(n, 99)) : "" })
    return data
  } catch {
    return null
  }
}

function _parseErrorDetail(rawText, parsedJson, status) {
  if (parsedJson && typeof parsedJson === "object") {
    if (typeof parsedJson.detail === "string" && parsedJson.detail.trim()) return parsedJson.detail
    if (typeof parsedJson.message === "string" && parsedJson.message.trim()) return parsedJson.message
    if (
      parsedJson.detail &&
      typeof parsedJson.detail === "object" &&
      typeof parsedJson.detail.detail === "string"
    ) {
      return parsedJson.detail.detail
    }
  }
  const text = String(rawText || "").trim()
  if (text) return text
  return `HTTP ${status}`
}

async function fetchVoiceTtsAudio({ text, agentId }) {
  const res = await authedFetch("/api/voice/tts", {
    method: "POST",
    headers: { Accept: "audio/mpeg" },
    body: JSON.stringify({
      text: String(text || ""),
      ...(agentId ? { agent_id: String(agentId) } : {}),
    }),
  })
  if (!res.ok) {
    const raw = await res.text().catch(() => "")
    let parsed = null
    try {
      parsed = raw ? JSON.parse(raw) : null
    } catch {
      parsed = null
    }
    const err = new Error(_parseErrorDetail(raw, parsed, res.status))
    err.status = res.status
    err.body = parsed
    throw err
  }
  const buf = await res.arrayBuffer()
  const bytes = new Uint8Array(buf)
  let binary = ""
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i])
  }
  return {
    contentType: res.headers.get("content-type") || "audio/mpeg",
    audioBase64: btoa(binary),
  }
}

chrome.runtime.onInstalled.addListener(() => {
  if (chrome.sidePanel?.setPanelBehavior) {
    chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: false }).catch(() => {})
  }
  chrome.alarms?.create("approvals-badge", { periodInMinutes: 1 })
  void refreshBadge()
})

chrome.runtime.onStartup?.addListener(() => {
  chrome.alarms?.create("approvals-badge", { periodInMinutes: 1 })
  void refreshBadge()
})

chrome.alarms?.onAlarm.addListener((alarm) => {
  if (alarm.name === "approvals-badge") void refreshBadge()
})

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  ;(async () => {
    try {
      if (message?.type === "GET_SESSION") {
        const cfg = await getSettings()
        if (!cfg.accessToken) {
          sendResponse({ ok: true, signedIn: false, cfg: { appBase: cfg.appBase } })
          return
        }
        const session = await apiFetch("/api/extension/session")
        sendResponse({ ok: true, signedIn: true, session, cfg })
        return
      }
      if (message?.type === "USAGE_SIGNAL") {
        try {
          const result = await apiFetch("/api/extension/usage-signal", {
            method: "POST",
            body: {
              pageUrl: message.pageUrl,
              surface: message.surface || null,
              invoked: message.invoked !== false,
              note: message.note || null,
              environment: (await getSettings()).environment,
            },
          })
          sendResponse({ ok: true, result })
        } catch (err) {
          sendResponse({
            ok: false,
            error: err instanceof Error ? err.message : String(err),
          })
        }
        return
      }
      if (message?.type === "ENRICH") {
        const result = await apiFetch("/api/extension/enrich", {
          method: "POST",
          body: {
            pageUrl: message.pageUrl,
            pageContext: message.pageContext || {},
            environment: (await getSettings()).environment,
          },
        })
        sendResponse({ ok: true, result })
        return
      }
      if (message?.type === "EXECUTE_ACTION") {
        const body = {
          pageUrl: message.pageUrl,
          environment: (await getSettings()).environment,
        }
        if (message.confirmationToken) {
          body.confirmationToken = message.confirmationToken
        } else {
          body.invokeAction = message.invokeAction
          body.params = message.params || {}
        }
        const result = await apiFetch("/api/extension/actions/execute", {
          method: "POST",
          body,
        })
        sendResponse({ ok: true, result })
        return
      }
      if (message?.type === "LIST_WORKFLOWS") {
        const result = await apiFetch(
          `/api/extension/workflows?environment=${encodeURIComponent((await getSettings()).environment)}`,
        )
        sendResponse({ ok: true, result })
        return
      }
      if (message?.type === "EXECUTE_WORKFLOW") {
        const body = {
          pageUrl: message.pageUrl,
          environment: (await getSettings()).environment,
        }
        if (message.confirmationToken) {
          body.confirmationToken = message.confirmationToken
        } else {
          body.workflowId = message.workflowId
          body.parameters = message.parameters || {}
        }
        const result = await apiFetch("/api/extension/workflows/execute", {
          method: "POST",
          body,
        })
        sendResponse({ ok: true, result })
        return
      }
      if (message?.type === "CHAT") {
        const result = await apiFetch("/api/extension/chat", {
          method: "POST",
          body: {
            message: message.message,
            pageUrl: message.pageUrl,
            pageContext: message.pageContext || {},
            conversationId: message.conversationId || null,
            spokenMode: Boolean(message.spokenMode),
            environment: (await getSettings()).environment,
          },
        })
        sendResponse({ ok: true, result })
        return
      }
      if (message?.type === "VOICE_STATUS") {
        try {
          const result = await apiFetch("/api/voice/status")
          const ttsEnabled = Boolean(result && result.tts_enabled)
          sendResponse({
            ok: true,
            status: result,
            enabled: ttsEnabled,
            blocked: false,
            reason: ttsEnabled ? null : "Voice output is not enabled for this workspace.",
          })
        } catch (err) {
          const status = Number(err?.status || 0)
          if (status === 403) {
            sendResponse({
              ok: true,
              status: null,
              enabled: false,
              blocked: true,
              reason: "Voice is turned off for this organization or your seat.",
            })
            return
          }
          sendResponse({
            ok: false,
            error: err instanceof Error ? err.message : String(err),
            status,
          })
        }
        return
      }
      if (message?.type === "VOICE_TTS") {
        const voiceText = String(message.text || "").trim()
        if (!voiceText) {
          sendResponse({ ok: false, error: "Voice text is required." })
          return
        }
        try {
          const audio = await fetchVoiceTtsAudio({
            text: voiceText,
            agentId: message.agentId || null,
          })
          sendResponse({ ok: true, ...audio })
        } catch (err) {
          sendResponse({
            ok: false,
            error: err instanceof Error ? err.message : String(err),
            status: Number(err?.status || 0),
          })
        }
        return
      }
      if (message?.type === "GET_ME") {
        sendResponse({ ok: true, me: await apiFetch("/api/auth/me") })
        return
      }
      if (message?.type === "LIST_APPROVALS") {
        const result = await refreshBadge()
        sendResponse({ ok: true, approvals: result?.approvals ?? (await apiFetch("/api/approvals"))?.approvals ?? [] })
        return
      }
      if (message?.type === "DECIDE_APPROVAL") {
        const id = encodeURIComponent(String(message.id || ""))
        const decision = message.approve ? "approve" : "reject"
        const result = await apiFetch(`/api/approvals/${id}/${decision}`, {
          method: "POST",
          body: message.approve ? {} : { comment: message.comment || null },
        })
        void refreshBadge()
        sendResponse({ ok: true, result })
        return
      }
      if (message?.type === "LIST_ACTIVITY") {
        const result = await apiFetch(`/api/activity/recent?limit=${Number(message.limit) || 30}`)
        sendResponse({ ok: true, events: result?.events || [] })
        return
      }
      if (message?.type === "LIST_CONVERSATIONS") {
        const result = await apiFetch("/api/conversations?limit=20")
        sendResponse({ ok: true, conversations: result?.conversations || [] })
        return
      }
      if (message?.type === "LOAD_MESSAGES") {
        const id = encodeURIComponent(String(message.conversationId || ""))
        const result = await apiFetch(`/api/conversations/${id}/messages?limit=40`)
        sendResponse({ ok: true, messages: result?.messages || [] })
        return
      }
      if (message?.type === "OPEN_APP") {
        const cfg = await getSettings()
        const path = String(message.path || "/home")
        const url = /^https?:\/\//.test(path) ? path : `${cfg.appBase}/${path.replace(/^\//, "")}`
        await chrome.tabs.create({ url })
        sendResponse({ ok: true })
        return
      }
      if (message?.type === "SIGN_OUT") {
        await chrome.storage.local.remove(["accessToken", "orgId", "refreshToken", "expiresAt"])
        await chrome.action.setBadgeText({ text: "" })
        sendResponse({ ok: true })
        return
      }
      if (message?.type === "OPEN_CONNECT") {
        const cfg = await getSettings()
        const extId = chrome.runtime.id
        const url = `${cfg.appBase}/extension/connect?ext_id=${encodeURIComponent(extId)}`
        await chrome.tabs.create({ url })
        sendResponse({ ok: true })
        return
      }
      if (message?.type === "INJECT_COMPANY_OVERLAY") {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
        if (!tab?.id) throw new Error("No active tab")
        await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          files: ["content/shared.js", "content/company.js"],
        })
        await chrome.scripting.insertCSS({
          target: { tabId: tab.id },
          files: ["content/overlay.css"],
        })
        sendResponse({ ok: true })
        return
      }
      sendResponse({ ok: false, error: "Unknown message" })
    } catch (err) {
      sendResponse({
        ok: false,
        error: err instanceof Error ? err.message : String(err),
        code: err?.code,
      })
    }
  })()
  return true
})

// Auth handoff from gravitre.app /extension/connect
chrome.runtime.onMessageExternal.addListener((message, _sender, sendResponse) => {
  ;(async () => {
    if (message?.type !== "GRAVITRE_AUTH" && message?.type !== "GRAVITREE_AUTH") {
      sendResponse({ ok: false })
      return
    }
    const token = String(message.accessToken || "").trim()
    const orgId = String(message.orgId || "").trim()
    if (!token || !orgId) {
      sendResponse({ ok: false, error: "Missing token or orgId" })
      return
    }
    const expiresAt = Number(message.expiresAt)
    await chrome.storage.local.set({
      accessToken: token,
      // Newer gravitre.app builds hand over a separate, renewable session.
      refreshToken: String(message.refreshToken || ""),
      expiresAt: Number.isFinite(expiresAt) && expiresAt > 0 ? expiresAt : null,
      orgId,
      environment: message.environment || "production",
      apiBase: message.apiBase || DEFAULT_API,
      appBase: message.appBase || DEFAULT_APP,
    })
    void refreshBadge()
    sendResponse({ ok: true })
  })()
  return true
})
