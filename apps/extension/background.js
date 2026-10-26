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

/** The session ran out: forget the tokens, keep the workspace so the popup can say which one expired. */
async function endSession() {
  await chrome.storage.local.remove(["accessToken", "refreshToken", "expiresAt"])
  await chrome.storage.local.set({ sessionExpired: true })
  await chrome.action.setBadgeText({ text: "" }).catch(() => {})
}

/**
 * The extension owns its own session (minted by /extension/connect), so it can
 * renew it here without touching the web app's session.
 */
async function refreshSession(cfg) {
  if (!cfg.refreshToken) {
    await endSession()
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
        await endSession()
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
      await endSession()
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

/** What the popup shows while offline: the last workspace, people and count we saw, with the time. */
async function saveSnapshot(patch) {
  const { snapshot } = await chrome.storage.local.get("snapshot")
  await chrome.storage.local.set({ snapshot: { ...(snapshot || {}), ...patch, at: new Date().toISOString() } })
}

function isOffline(err) {
  return err instanceof TypeError || (typeof navigator !== "undefined" && navigator.onLine === false)
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
    await saveSnapshot({ approvals: n })
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

/** Alt+G opens the side panel on the current tab. */
chrome.commands?.onCommand.addListener((command, tab) => {
  if (command !== "open-side-panel") return
  const open = (t) => t?.id != null && chrome.sidePanel?.open({ tabId: t.id }).catch(() => {})
  if (tab) open(tab)
  else chrome.tabs.query({ active: true, currentWindow: true }).then(([t]) => open(t))
})

/** Content scripts for sites the person added themselves (Settings, Add a site). */
function siteScriptId(host) {
  return `gv-site-${host.replace(/[^a-z0-9.-]/gi, "")}`
}

async function registerSite(host) {
  const id = siteScriptId(host)
  const existing = await chrome.scripting.getRegisteredContentScripts({ ids: [id] })
  if (existing.length) return
  await chrome.scripting.registerContentScripts([
    {
      id,
      matches: [`https://${host}/*`],
      js: ["content/shared.js", "content/company.js"],
      css: ["content/overlay.css"],
      runAt: "document_idle",
      persistAcrossSessions: true,
    },
  ])
}

async function unregisterSite(host) {
  await chrome.scripting.unregisterContentScripts({ ids: [siteScriptId(host)] }).catch(() => {})
  await chrome.permissions.remove({ origins: [`https://${host}/*`] }).catch(() => {})
}

const env = async () => (await getSettings()).environment

const HANDLERS = {
  /** Who is signed in, to which workspace, or why not: signed out, expired, no access, offline. */
  async GET_SESSION() {
    const cfg = await getSettings()
    const { sessionExpired, snapshot } = await chrome.storage.local.get(["sessionExpired", "snapshot"])
    if (!cfg.accessToken) {
      return { signedIn: false, expired: Boolean(sessionExpired), snapshot: snapshot || null, cfg: { appBase: cfg.appBase } }
    }
    try {
      const [session, me] = await Promise.all([apiFetch("/api/extension/session"), apiFetch("/api/auth/me").catch(() => null)])
      const org = me?.organizations?.find((o) => o.id === cfg.orgId) || me?.current_org || null
      const profile = {
        email: me?.email || me?.user?.email || "",
        name: me?.user?.full_name || "",
        orgName: org?.name || snapshot?.profile?.orgName || "",
        organizations: Array.isArray(me?.organizations) ? me.organizations : [],
      }
      await saveSnapshot({ profile, connected: session?.connectedIntegrations || [] })
      return { signedIn: true, session, profile, cfg: { appBase: cfg.appBase, orgId: cfg.orgId } }
    } catch (err) {
      if (err?.code === "not_authenticated") {
        return { signedIn: false, expired: true, snapshot: snapshot || null, cfg: { appBase: cfg.appBase } }
      }
      if (Number(err?.status) === 403) {
        const me = await apiFetch("/api/auth/me").catch(() => null)
        return {
          signedIn: true,
          noAccess: true,
          snapshot: snapshot || null,
          organizations: Array.isArray(me?.organizations) ? me.organizations : [],
          cfg: { appBase: cfg.appBase, orgId: cfg.orgId },
        }
      }
      if (isOffline(err)) return { signedIn: true, offline: true, snapshot: snapshot || null, cfg: { appBase: cfg.appBase } }
      throw err
    }
  },

  async SWITCH_ORG(message) {
    const orgId = String(message.orgId || "").trim()
    if (!orgId) throw new Error("Pick a workspace")
    await chrome.storage.local.set({ orgId })
    await chrome.storage.local.remove("snapshot")
    void refreshBadge()
    return {}
  },

  async USAGE_SIGNAL(message) {
    const result = await apiFetch("/api/extension/usage-signal", {
      method: "POST",
      body: {
        pageUrl: message.pageUrl,
        surface: message.surface || null,
        invoked: message.invoked !== false,
        note: message.note || null,
        environment: await env(),
      },
    })
    return { result }
  },

  async ENRICH(message) {
    const result = await apiFetch("/api/extension/enrich", {
      method: "POST",
      body: { pageUrl: message.pageUrl, pageContext: message.pageContext || {}, environment: await env() },
    })
    return { result }
  },

  async EXECUTE_ACTION(message) {
    const body = { pageUrl: message.pageUrl, environment: await env() }
    if (message.confirmationToken) body.confirmationToken = message.confirmationToken
    else {
      body.invokeAction = message.invokeAction
      body.params = message.params || {}
    }
    return { result: await apiFetch("/api/extension/actions/execute", { method: "POST", body }) }
  },

  async LIST_WORKFLOWS() {
    return { result: await apiFetch(`/api/extension/workflows?environment=${encodeURIComponent(await env())}`) }
  },

  async EXECUTE_WORKFLOW(message) {
    const body = { pageUrl: message.pageUrl, environment: await env() }
    if (message.confirmationToken) body.confirmationToken = message.confirmationToken
    else {
      body.workflowId = message.workflowId
      body.parameters = message.parameters || {}
    }
    return { result: await apiFetch("/api/extension/workflows/execute", { method: "POST", body }) }
  },

  async CHAT(message) {
    const result = await apiFetch("/api/extension/chat", {
      method: "POST",
      body: {
        message: message.message,
        pageUrl: message.pageUrl,
        pageContext: message.pageContext || {},
        conversationId: message.conversationId || null,
        agentId: message.agentId || null,
        spokenMode: Boolean(message.spokenMode),
        environment: await env(),
      },
    })
    return { result }
  },

  async VOICE_STATUS() {
    try {
      const result = await apiFetch("/api/voice/status")
      const ttsEnabled = Boolean(result && result.tts_enabled)
      return { status: result, enabled: ttsEnabled, blocked: false, reason: ttsEnabled ? null : "Voice output is not enabled for this workspace." }
    } catch (err) {
      if (Number(err?.status || 0) === 403) {
        return { status: null, enabled: false, blocked: true, reason: "Voice is turned off for this organization or your seat." }
      }
      throw err
    }
  },

  async VOICE_TTS(message) {
    const voiceText = String(message.text || "").trim()
    if (!voiceText) throw new Error("Voice text is required.")
    return await fetchVoiceTtsAudio({ text: voiceText, agentId: message.agentId || null })
  },

  async GET_ME() {
    return { me: await apiFetch("/api/auth/me") }
  },

  /** What this person's role can do; "approve_writes" gates the Approve buttons. */
  async GET_CAPS() {
    const body = await apiFetch("/api/org/role-permissions")
    const caps = Array.isArray(body?.my_capabilities) ? body.my_capabilities.map(String) : []
    return { role: body?.my_role || null, capabilities: caps }
  },

  async LIST_AGENTS() {
    const body = await apiFetch("/api/agents")
    return { agents: Array.isArray(body) ? body : body?.agents || [] }
  },

  async LIST_APPROVALS() {
    const result = await refreshBadge()
    return { approvals: result?.approvals ?? (await apiFetch("/api/approvals"))?.approvals ?? [] }
  },

  async DECIDE_APPROVAL(message) {
    const id = encodeURIComponent(String(message.id || ""))
    const decision = message.approve ? "approve" : "reject"
    const result = await apiFetch(`/api/approvals/${id}/${decision}`, {
      method: "POST",
      body: message.approve ? {} : { comment: message.comment || null },
    })
    void refreshBadge()
    return { result }
  },

  async LIST_ACTIVITY(message) {
    const result = await apiFetch(`/api/activity/recent?limit=${Number(message.limit) || 30}`)
    return { events: result?.events || [] }
  },

  async LIST_JOBS(message) {
    const result = await apiFetch(`/api/agent-jobs?limit=${Number(message.limit) || 20}`)
    return { jobs: Array.isArray(result?.jobs) ? result.jobs : [] }
  },

  async LIST_CONVERSATIONS() {
    const result = await apiFetch("/api/conversations?limit=20")
    return { conversations: result?.conversations || [] }
  },

  async LOAD_MESSAGES(message) {
    const id = encodeURIComponent(String(message.conversationId || ""))
    const result = await apiFetch(`/api/conversations/${id}/messages?limit=40`)
    return { messages: result?.messages || [] }
  },

  async OPEN_APP(message) {
    const cfg = await getSettings()
    const path = String(message.path || "/home")
    const url = /^https?:\/\//.test(path) ? path : `${cfg.appBase}/${path.replace(/^\//, "")}`
    await chrome.tabs.create({ url })
    return {}
  },

  /** From the in-page button or card: open the panel on that tab, optionally with a question ready. */
  async OPEN_SIDE_PANEL(message, sender) {
    if (message.draft) await chrome.storage.local.set({ gvDraft: { text: String(message.draft), at: Date.now() } })
    const tabId = sender?.tab?.id ?? message.tabId
    if (tabId == null) throw new Error("No tab to open the side panel on")
    await chrome.sidePanel.open({ tabId })
    return {}
  },

  async SIGN_OUT() {
    await chrome.storage.local.remove(["accessToken", "orgId", "refreshToken", "expiresAt", "sessionExpired", "snapshot"])
    await chrome.action.setBadgeText({ text: "" })
    return {}
  },

  async OPEN_CONNECT() {
    const cfg = await getSettings()
    const url = `${cfg.appBase}/extension/connect?ext_id=${encodeURIComponent(chrome.runtime.id)}`
    await chrome.tabs.create({ url })
    return {}
  },

  async REGISTER_SITE(message) {
    const host = String(message.host || "").trim().toLowerCase()
    if (!/^[a-z0-9.-]+\.[a-z]{2,}$/.test(host)) throw new Error("Enter a site like app.hubspot.com")
    if (message.remove) await unregisterSite(host)
    else await registerSite(host)
    return {}
  },

  async INJECT_COMPANY_OVERLAY() {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
    if (!tab?.id) throw new Error("No active tab")
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["content/shared.js", "content/company.js"] })
    await chrome.scripting.insertCSS({ target: { tabId: tab.id }, files: ["content/overlay.css"] })
    return {}
  },
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const handler = HANDLERS[message?.type]
  if (!handler) return false
  ;(async () => {
    try {
      sendResponse({ ok: true, ...((await handler(message, sender)) || {}) })
    } catch (err) {
      sendResponse({
        ok: false,
        error: err instanceof Error ? err.message : String(err),
        code: err?.code,
        status: Number(err?.status || 0),
        offline: isOffline(err),
      })
    }
  })()
  return true
})

// gravitre.app /extension/connect: PING to see the extension is installed, GRAVITRE_AUTH to hand over a session.
chrome.runtime.onMessageExternal.addListener((message, _sender, sendResponse) => {
  ;(async () => {
    if (message?.type === "PING") {
      sendResponse({ ok: true, version: chrome.runtime.getManifest().version })
      return
    }
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
      sessionExpired: false,
    })
    void refreshBadge()
    sendResponse({ ok: true })
  })()
  return true
})
