/**
 * Gravitre extension service worker — API calls + auth storage.
 *
 * Ported from the original background.js with its request/response contracts
 * intact. Two things here are wire contracts and must not be "cleaned up":
 *
 * 1. `GRAVITREE_AUTH` — the message the deployed gravitre.app /extension/connect
 *    page posts to this extension. The product is spelled "Gravitre", but
 *    renaming this string would break sign-in for every already-shipped web
 *    build, so it stays until both sides ship together.
 * 2. The `confirmationToken` branches — when a token is present the server
 *    re-derives the action server-side, so the client must NOT also send
 *    invokeAction/params. Sending both is what would let a tampered client
 *    execute something other than what was approved.
 */

const DEFAULT_API = "https://gravitre-saas-backend-production.up.railway.app"
const DEFAULT_APP = "https://gravitre.app"

type Settings = {
  accessToken: string
  orgId: string
  environment: string
  apiBase: string
  appBase: string
}

type ApiError = Error & { code?: string; status?: number; body?: unknown }

async function getSettings(): Promise<Settings> {
  const data = await chrome.storage.local.get([
    "accessToken",
    "orgId",
    "environment",
    "apiBase",
    "appBase",
  ])
  const str = (v: unknown, fallback = "") =>
    typeof v === "string" && v ? v : fallback
  return {
    accessToken: str(data.accessToken),
    orgId: str(data.orgId),
    environment: str(data.environment, "production"),
    apiBase: str(data.apiBase, DEFAULT_API).replace(/\/+$/, ""),
    appBase: str(data.appBase, DEFAULT_APP).replace(/\/+$/, ""),
  }
}

async function apiFetch(
  path: string,
  { method = "GET", body }: { method?: string; body?: unknown } = {},
): Promise<any> {
  const cfg = await getSettings()
  if (!cfg.accessToken || !cfg.orgId) {
    const err = new Error(
      "Not signed in. Open the extension and connect Gravitre.",
    ) as ApiError
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
  let json: any = null
  try {
    json = text ? JSON.parse(text) : null
  } catch {
    json = { detail: text }
  }
  if (!res.ok) {
    const err = new Error(
      (json && (json.detail || json.message)) || `HTTP ${res.status}`,
    ) as ApiError
    err.status = res.status
    err.body = json
    throw err
  }
  return json
}

chrome.runtime.onInstalled.addListener(() => {
  if (chrome.sidePanel?.setPanelBehavior) {
    chrome.sidePanel
      .setPanelBehavior({ openPanelOnActionClick: false })
      .catch(() => {})
  }
})

chrome.runtime.onMessage.addListener((message: any, _sender, sendResponse) => {
  void (async () => {
    try {
      const env = async () => (await getSettings()).environment

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
        // Best-effort telemetry: never surface a failure to the user.
        try {
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
            environment: await env(),
          },
        })
        sendResponse({ ok: true, result })
        return
      }

      if (message?.type === "EXECUTE_ACTION") {
        const body: Record<string, unknown> = {
          pageUrl: message.pageUrl,
          environment: await env(),
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
          `/api/extension/workflows?environment=${encodeURIComponent(await env())}`,
        )
        sendResponse({ ok: true, result })
        return
      }

      if (message?.type === "EXECUTE_WORKFLOW") {
        const body: Record<string, unknown> = {
          pageUrl: message.pageUrl,
          environment: await env(),
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
            environment: await env(),
          },
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
        // Single bundled IIFE now; it carries its own styles into a shadow root,
        // so there is no separate insertCSS step (which would have leaked
        // styles into the host page).
        await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          files: ["content/overlay.js"],
        })
        // No OPEN_OVERLAY message here: a freshly injected bundle opens itself
        // on evaluation (mirroring the old content/company.js IIFE). Sending
        // one as well would mount the card twice.
        sendResponse({ ok: true })
        return
      }

      sendResponse({ ok: false, error: "Unknown message" })
    } catch (err) {
      sendResponse({
        ok: false,
        error: err instanceof Error ? err.message : String(err),
        code: (err as ApiError)?.code,
      })
    }
  })()
  return true
})

// Auth handoff from gravitre.app /extension/connect. See note above: the
// message type string is a deployed contract.
chrome.runtime.onMessageExternal.addListener((message: any, _sender, sendResponse) => {
  void (async () => {
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
