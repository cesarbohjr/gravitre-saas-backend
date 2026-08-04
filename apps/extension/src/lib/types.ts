/**
 * Response shapes for the extension API.
 *
 * These are transcribed from backend/app/routers/extension.py and the existing
 * service worker contracts. This is a presentation-only redesign, so nothing
 * here may add, rename or drop a field — the types exist so the UI can only
 * render data the server actually returns.
 */

export type Session = {
  userId: string
  orgId: string
  role: string
  connectedIntegrations: string[]
  allowedActions: string[]
  model: string
  openAppUrl: string
}

export type Extracted = {
  fullName?: string
  firstName?: string
  lastName?: string
  title?: string
  company?: string
  email?: string
}

export type EnrichMatch = {
  action: string
  success: boolean
  confidenceLabel?: string
  error?: string
  data?: Record<string, unknown>
}

export type Suggestion = {
  label: string
  invokeAction: string
  params?: Record<string, unknown>
  note?: string
}

export type EnrichResult = {
  surface?: string
  extracted?: Extracted
  matches?: EnrichMatch[]
  suggestions?: Suggestion[]
  connectedIntegrations?: string[]
  voiceNote?: string
  openInGravitreeUrl?: string
}

/** `needs_confirmation` is the server telling us a write is gated. */
export type ExecuteResult = {
  status?: "needs_confirmation" | string
  confirmationToken?: string
  params?: Record<string, unknown>
  success?: boolean
  invokeAction?: string
  error?: string
  runId?: string
  outcomeId?: string
  outcomeUrl?: string
}

export type WorkflowStep = {
  name: string
  action?: string
}

export type ExtensionWorkflow = {
  id: string
  name: string
  stepCount: number
  progressSteps?: WorkflowStep[]
}

export type WorkflowExecuteResult = {
  status?: string
  confirmationToken?: string
  runId?: string
  error?: string
}

export type ChatResult = {
  answer?: string
  conversationId?: string
  needsHandoff?: boolean
  openInGravitreeUrl?: string
}

/** Envelope every `chrome.runtime.sendMessage` handler replies with. */
export type Envelope<T> = {
  ok: boolean
  error?: string
  code?: string
  result?: T
}

export type SessionEnvelope = {
  ok: boolean
  signedIn?: boolean
  error?: string
  session?: Session
  cfg?: { appBase: string }
}

/**
 * Every surface the extension runs on. The first five have manifest-declared
 * content scripts; `company` is any other page, reached on demand via
 * activeTab injection; `unknown` is a URL we cannot act on at all (chrome://,
 * about:, the store, etc).
 */
export type Surface =
  | "linkedin"
  | "gmail"
  | "outlook"
  | "salesforce"
  | "slack"
  | "company"
  | "unknown"

/**
 * What the content script scrapes from the host page and sends to /enrich.
 *
 * Field names match what the old content/*.js extractors produced, so the
 * backend contract is unchanged. Everything except `surface` and `url` is
 * optional because each host page exposes a different subset — the UI must
 * render only what is actually present rather than showing empty rows.
 */
export type PageContext = {
  surface: Surface
  url: string
  companyName?: string
  personName?: string
  title?: string
  industry?: string
  email?: string
  emailDomain?: string
  domain?: string
  subject?: string
  channel?: string
  /** Only set for `company_site`: distinguishes a careers/about page. */
  pageKind?: "careers_about" | "company_site"
}
