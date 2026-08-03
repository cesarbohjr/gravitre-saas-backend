/** Gravitree extension service worker — API calls + auth storage. */

const DEFAULT_API =
  "https://gravitre-saas-backend-production.up.railway.app"
const DEFAULT_APP = "https://gravitre.app"

async function getSettings() {
  const data = await chrome.storage.local.get([
    "accessToken",
    "orgId",
    "environment",
    "apiBase",
    "appBase",
  ])
  return {
    accessToken: data.accessToken || "",
    orgId: data.orgId || "",
    environment: data.environment || "production",
    apiBase: (data.apiBase || DEFAULT_API).replace(/\/+$/, ""),
    appBase: (data.appBase || DEFAULT_APP).replace(/\/+$/, ""),
  }
}

async function apiFetch(path, { method = "GET", body } = {}) {
  const cfg = await getSettings()
  if (!cfg.accessToken || !cfg.orgId) {
    const err = new Error("Not signed in. Open the extension and connect Gravitree.")
    err.code = "not_authenticated"
    throw err
  }
  const res = await fetch(`${cfg.apiBase}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${cfg.accessToken}`,
      "Content-Type": "application/json",
      "X-Org-Id": cfg.orgId,
      "X-Environment": cfg.environment,
    },
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
      (json && (json.detail || json.message)) || `HTTP ${res.status}`,
    )
    err.status = res.status
    err.body = json
    throw err
  }
  return json
}

chrome.runtime.onInstalled.addListener(() => {
  if (chrome.sidePanel?.setPanelBehavior) {
    chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: false }).catch(() => {})
  }
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
      if (message?.type === "SIGN_OUT") {
        await chrome.storage.local.remove(["accessToken", "orgId", "refreshToken"])
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
    if (message?.type !== "GRAVITREE_AUTH") {
      sendResponse({ ok: false })
      return
    }
    const token = String(message.accessToken || "").trim()
    const orgId = String(message.orgId || "").trim()
    if (!token || !orgId) {
      sendResponse({ ok: false, error: "Missing token or orgId" })
      return
    }
    await chrome.storage.local.set({
      accessToken: token,
      orgId,
      environment: message.environment || "production",
      apiBase: message.apiBase || DEFAULT_API,
      appBase: message.appBase || DEFAULT_APP,
    })
    sendResponse({ ok: true })
  })()
  return true
})
