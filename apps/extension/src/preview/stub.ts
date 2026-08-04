/**
 * Visual-harness only. Stubs the chrome APIs the UI touches so the popup, side
 * panel and overlay can be rendered in a normal browser tab for light/dark
 * review. Payload shapes are copied from backend/app/routers/extension.py so
 * what we review matches what ships.
 *
 * This file is never referenced by the extension build — only by preview.html.
 */
import manifest from "../../manifest.json"

type Scenario = "connected" | "disconnected"

const params = new URLSearchParams(location.search)
const scenario = (params.get("scenario") as Scenario) || "connected"

const SESSION = {
  signedIn: true,
  orgId: "org_7f3c9a21b4e8",
  userId: "usr_2c81",
  role: "admin",
  environment: "production",
  connectedIntegrations: ["hubspot", "apollo", "slack"],
  allowedActions: [
    "hubspot.contact.create",
    "hubspot.contact.update",
    "hubspot.note.create",
    "apollo.person.enrich",
    "slack.message.post",
  ],
  openAppUrl: "https://gravitre.app",
}

const listeners: Array<(...a: any[]) => void> = []

const chromeStub = {
  runtime: {
    id: "preview-extension-id",
    getManifest: () => manifest as any,
    sendMessage: (msg: any, cb?: (r: any) => void) => {
      const respond = (r: any) => cb?.(r)
      if (msg?.type === "GET_SESSION") {
        if (scenario === "disconnected") {
          return respond({ ok: true, signedIn: false, cfg: { appBase: "https://gravitre.app" } })
        }
        return respond({ ok: true, signedIn: true, session: SESSION })
      }
      if (msg?.type === "USAGE_SIGNAL") return respond({ ok: true })
      return respond({ ok: true })
    },
    lastError: undefined as { message?: string } | undefined,
  },
  storage: {
    local: {
      get: async () => ({}),
      set: async () => {},
      remove: async () => {},
    },
  },
  tabs: {
    query: async () => [
      { id: 1, windowId: 1, active: true, url: "https://www.linkedin.com/in/jane-doe-cto/" },
    ],
    sendMessage: () => {},
    onActivated: { addListener: (f: any) => listeners.push(f), removeListener: () => {} },
    onUpdated: { addListener: (f: any) => listeners.push(f), removeListener: () => {} },
  },
  sidePanel: { open: async () => {} },
  scripting: { executeScript: async () => {}, insertCSS: async () => {} },
}

;(globalThis as any).chrome = chromeStub
