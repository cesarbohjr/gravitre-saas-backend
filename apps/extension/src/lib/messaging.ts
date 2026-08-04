import type {
  ChatResult,
  EnrichResult,
  Envelope,
  ExecuteResult,
  ExtensionWorkflow,
  SessionEnvelope,
  Surface,
  WorkflowExecuteResult,
} from "./types"

/**
 * Typed wrappers over chrome.runtime.sendMessage.
 *
 * The message `type` strings and body fields below are byte-for-byte the ones
 * the existing service worker already handles. This layer only adds types and
 * promisification — it deliberately does not reshape, retry, or add any
 * request the worker does not already implement.
 */
function send<T>(message: Record<string, unknown>): Promise<T> {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage(message, (response) => {
      // A closed port (popup dismissed mid-flight) surfaces here rather than
      // throwing an unhandled error into the page.
      const lastError = chrome.runtime.lastError
      if (lastError) {
        resolve({ ok: false, error: lastError.message } as T)
        return
      }
      resolve((response ?? { ok: false, error: "No response" }) as T)
    })
  })
}

export function getSession() {
  return send<SessionEnvelope>({ type: "GET_SESSION" })
}

export function signOut() {
  return send<Envelope<never>>({ type: "SIGN_OUT" })
}

export function openConnect() {
  return send<Envelope<never>>({ type: "OPEN_CONNECT" })
}

export function enrich(pageUrl: string, pageContext: Record<string, unknown>) {
  return send<Envelope<EnrichResult>>({ type: "ENRICH", pageUrl, pageContext })
}

export function listWorkflows() {
  return send<Envelope<{ workflows: ExtensionWorkflow[]; count: number }>>({
    type: "LIST_WORKFLOWS",
  })
}

/**
 * Stage a write. Called WITHOUT a token, this asks the server to validate the
 * action and issue one; the server replies `status: "needs_confirmation"`.
 */
export function proposeAction(args: {
  invokeAction: string
  params: Record<string, unknown>
  pageUrl: string
}) {
  return send<Envelope<ExecuteResult>>({ type: "EXECUTE_ACTION", ...args })
}

/**
 * Commit a write using a token the SERVER issued. There is deliberately no
 * code path that synthesises a token client-side.
 */
export function executeAction(args: { confirmationToken: string; pageUrl: string }) {
  return send<Envelope<ExecuteResult>>({ type: "EXECUTE_ACTION", ...args })
}

export function proposeWorkflow(args: {
  workflowId: string
  pageUrl: string
  parameters: Record<string, unknown>
}) {
  return send<Envelope<WorkflowExecuteResult>>({ type: "EXECUTE_WORKFLOW", ...args })
}

export function executeWorkflow(args: { confirmationToken: string; pageUrl: string }) {
  return send<Envelope<WorkflowExecuteResult>>({ type: "EXECUTE_WORKFLOW", ...args })
}

export function chat(args: {
  message: string
  pageUrl: string
  pageContext: Record<string, unknown>
  conversationId: string | null
}) {
  return send<Envelope<ChatResult>>({ type: "CHAT", ...args })
}

export function usageSignal(args: {
  pageUrl: string
  invoked: boolean
  note?: string
  surface?: string
}) {
  return send<Envelope<unknown>>({ type: "USAGE_SIGNAL", ...args })
}

export function injectCompanyOverlay() {
  return send<Envelope<never>>({ type: "INJECT_COMPANY_OVERLAY" })
}

/** Host patterns that have a registered content script, mirroring the manifest. */
const SURFACE_PATTERNS: Array<[Surface, RegExp]> = [
  ["linkedin", /linkedin\.com/i],
  ["gmail", /mail\.google\.com/i],
  ["outlook", /outlook\.(office|live|office365)\./i],
  ["salesforce", /(lightning\.force\.com|salesforce\.com|force\.com)/i],
  ["slack", /app\.slack\.com/i],
]

export function surfaceForUrl(url: string): Surface {
  for (const [surface, pattern] of SURFACE_PATTERNS) {
    if (pattern.test(url)) return surface
  }
  return "unknown"
}

export const SURFACE_LABELS: Record<Surface, string> = {
  linkedin: "LinkedIn",
  gmail: "Gmail",
  outlook: "Outlook",
  salesforce: "Salesforce",
  slack: "Slack",
  company: "Company page",
  unknown: "This page",
}
