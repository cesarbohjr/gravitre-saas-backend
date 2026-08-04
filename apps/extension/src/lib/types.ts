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

/**
 * The identity fields the server echoed back. Values are `null` (not absent)
 * when the page did not yield them, so the UI must treat null as "not found".
 */
export type Extracted = {
  fullName?: string | null
  firstName?: string | null
  lastName?: string | null
  email?: string | null
  company?: string | null
  domain?: string | null
  title?: string | null
}

export type EnrichMatch = {
  action: string
  success: boolean
  confidenceLabel?: string
  error?: string
  data?: Record<string, unknown>
}

export type Suggestion = {
  id?: string
  label: string
  invokeAction: string
  kind?: string
  /**
   * Server-computed, via `invoke_action_requires_write_approval`. This is the
   * authoritative answer to "does this need the approval gate?" — the UI must
   * not re-derive it from the action name.
   */
  requiresApproval?: boolean
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
 * What the content script scrapes from the host page and posts to /extension/enrich.
 *
 * These key names are a WIRE CONTRACT, not a local convention:
 * `enrich_from_page_context` reads `fullName`, `firstName`, `lastName`, `email`,
 * `company`, `domain` and `title`, and `extension_enrich` reads `source` for
 * the usage signal. Renaming any of them (e.g. to `personName`/`companyName`)
 * silently returns an empty enrichment, because the server finds no identity
 * fields to match on. Every field is optional because each host page exposes a
 * different subset.
 */
export type PageContext = {
  fullName?: string
  firstName?: string
  lastName?: string
  email?: string
  company?: string
  domain?: string
  title?: string
  linkedinUrl?: string
  /** Surface id the backend records against the usage signal. */
  source?: string
  /** Only set on a non-declared site: flags a careers/about page. */
  pageKind?: "careers_about" | "company_site"
}
