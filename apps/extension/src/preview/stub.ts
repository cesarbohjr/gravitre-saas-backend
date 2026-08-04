/**
 * Visual-harness only. Stubs the chrome APIs the UI touches so the popup, side
 * panel and overlay can be rendered in a normal browser tab for light/dark
 * review. Payload shapes are copied from backend/app/routers/extension.py so
 * what we review matches what ships.
 *
 * This file is never referenced by the extension build — only by preview.html.
 */
// The real manifest, so the permission disclosure under review shows the same
// hosts the shipped extension actually requests.
import manifest from "../../public/manifest.json"

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

/** Shapes copied from extension_bridge_service.enrich_from_page_context. */
const ENRICH = {
  surface: "linkedin",
  pageUrl: "https://www.linkedin.com/in/jane-doe-cto/",
  extracted: {
    fullName: "Jane Doe",
    firstName: "Jane",
    lastName: "Doe",
    email: "jane.doe@northwind.io",
    company: "Northwind Logistics",
    domain: "northwind.io",
    title: "Chief Technology Officer",
  },
  matches: [
    {
      action: "apollo.people.match",
      success: true,
      data: { person: { id: "apl_88213" } },
      confidenceLabel: "matched",
    },
    {
      action: "hubspot.contacts.search",
      success: false,
      error: "No contact with that email",
      data: {},
      confidenceLabel: "unavailable",
    },
  ],
  suggestions: [
    {
      id: "hs_create",
      label: "Create HubSpot contact",
      invokeAction: "hubspot.contact.create",
      kind: "write",
      requiresApproval: true,
      params: {
        email: "jane.doe@northwind.io",
        firstname: "Jane",
        lastname: "Doe",
        company: "Northwind Logistics",
        jobtitle: "Chief Technology Officer",
      },
      note: "Not found in HubSpot — this creates a new record.",
    },
    {
      id: "hs_note",
      label: "Log a note",
      invokeAction: "hubspot.note.create",
      kind: "write",
      requiresApproval: true,
      params: { body: "Reviewed profile from LinkedIn." },
    },
  ],
  connectedIntegrations: ["hubspot", "apollo", "slack"],
  voiceNote: "Jane Doe leads engineering at Northwind Logistics.",
  openInGravitreeUrl: "/ai?contact=apl_88213",
}

const WORKFLOWS = [
  {
    id: "wf_inbound",
    name: "Inbound lead triage",
    stepCount: 3,
    progressSteps: [
      { name: "Enrich contact", action: "apollo.person.enrich" },
      { name: "Create CRM record", action: "hubspot.contact.create" },
      { name: "Notify #sales", action: "slack.message.post" },
    ],
  },
  { id: "wf_qbr", name: "Draft QBR summary", stepCount: 2 },
]

const listeners: Array<(...a: any[]) => void> = []

const chromeStub = {
  runtime: {
    id: "preview-extension-id",
    getManifest: () => manifest as any,
    sendMessage: (msg: any, cb?: (r: any) => void) => {
      // Async on purpose: the real worker round-trips to FastAPI, so replying
      // synchronously would skip every loading state we need to review.
      const respond = (r: any) => setTimeout(() => cb?.(r), 350)

      if (msg?.type === "GET_SESSION") {
        if (scenario === "disconnected") {
          return respond({ ok: true, signedIn: false, cfg: { appBase: "https://gravitre.app" } })
        }
        return respond({ ok: true, signedIn: true, session: SESSION })
      }

      if (msg?.type === "ENRICH") {
        if (scenario === "disconnected") {
          // Mirrors the no-connector early return in extension_enrich.
          return respond({
            ok: true,
            result: {
              surface: "unknown",
              matches: [],
              suggestions: [],
              connectedIntegrations: [],
              voiceNote: "Connect Apollo or HubSpot in Gravitre to enrich this page.",
              openInGravitreeUrl: "/connectors",
            },
          })
        }
        return respond({ ok: true, result: ENRICH })
      }

      if (msg?.type === "LIST_WORKFLOWS") {
        return respond({
          ok: true,
          result: { workflows: scenario === "disconnected" ? [] : WORKFLOWS, count: 2 },
        })
      }

      // The write gate is two calls on ONE type: no token → staged proposal,
      // token → execution. Modelled exactly so the approval panel is exercised.
      if (msg?.type === "EXECUTE_ACTION" || msg?.type === "EXECUTE_WORKFLOW") {
        if (!msg.confirmationToken) {
          return respond({
            ok: true,
            result: {
              status: "needs_confirmation",
              confirmationToken: "tok_preview_9f21",
              params: msg.params || ENRICH.suggestions[0].params,
            },
          })
        }
        return respond({
          ok: true,
          result: {
            status: "executed",
            success: true,
            invokeAction: msg.action || "hubspot.contact.create",
            runId: "run_5c02",
            outcomeUrl: "/runs/run_5c02",
          },
        })
      }

      if (msg?.type === "CHAT") {
        return respond({
          ok: true,
          result: {
            answer:
              "Jane Doe is CTO at Northwind Logistics, a 400-person 3PL. She is not yet in HubSpot — the suggestion above will create her record.",
            conversationId: "conv_preview_1",
            needsHandoff: true,
            openInGravitreeUrl: "/ai?conversation=conv_preview_1",
          },
        })
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
