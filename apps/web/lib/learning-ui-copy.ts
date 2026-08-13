/**
 * Operator-facing labels for Learning (all tabs).
 * Keep ICP language — avoid snake_case / backend jargon in the UI.
 */

const PACK_LABELS: Record<string, string> = {
  cybersecurity: "Cybersecurity",
  finance: "Finance",
  hr: "People & HR",
  legal: "Legal & compliance",
  marketing: "Marketing",
  sales: "Sales",
  revops: "Revenue operations",
  cs: "Customer success",
  msp: "MSP",
  executive: "Executive",
}

const TOPIC_LABELS: Record<string, string> = {
  edgar: "SEC filings (EDGAR)",
  employment_law: "employment law",
  ftc: "FTC guidance",
  can_spam: "CAN-SPAM / email rules",
  flsa: "wage & hour (FLSA)",
  fmla: "leave (FMLA)",
  nvd: "vulnerability advisories (NVD)",
  cisa_kev: "known exploited vulnerabilities",
}

const SURFACE_LABELS: Record<string, string> = {
  chat: "Chat",
  agent: "Agent",
  workflow: "Workflow",
  ai: "Gravitre AI",
  gravitre_ai: "Gravitre AI",
  governed_chat: "Guided chat",
  react: "Agent run",
}

const STAGE_LABELS: Record<string, string> = {
  memory: "Memory",
  knowledge: "Knowledge",
  retrieval: "Search",
  plan: "Plan",
  act: "Act",
  validate: "Validate",
  respond: "Respond",
  tool: "Tools",
  rerank: "Rerank",
  embed: "Embed",
}

export function packDisplayName(packId: string): string {
  const raw = packId.replace(/^pack\./i, "").trim().toLowerCase()
  return PACK_LABELS[raw] ?? raw.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}

/** Turn gap strings like `pack.legal: coverage weak on employment_law` into plain English. */
export function humanizeKnowledgeGap(gap: string): string {
  const text = (gap || "").trim()
  if (!text) return ""
  const m = text.match(/^pack\.([a-z0-9_]+):\s*(.+)$/i)
  const pack = m ? packDisplayName(m[1]) : null
  let rest = (m ? m[2] : text).trim()
  rest = rest
    .replace(/\blicense-verified\b/gi, "license-checked sources")
    .replace(/\bcoverage weak on\b/gi, "thin coverage for")
    .replace(/\bnot all sources verified\b/gi, "some sources still need license review")
    .replace(/\b\(not all sources verified\)\b/gi, "(some sources still need review)")
  rest = rest.replace(/\b([a-z][a-z0-9_]*)\b/gi, (token) => {
    const key = token.toLowerCase()
    return TOPIC_LABELS[key] ?? token.replace(/_/g, " ")
  })
  return pack ? `${pack}: ${rest}` : rest
}

export function relationshipTypeLabel(value: unknown): string {
  const raw = String(value ?? "")
    .trim()
    .replace(/_/g, " ")
  if (!raw) return "related to"
  return raw
}

export function entityTypeLabel(value: unknown): string {
  const raw = String(value ?? "")
    .trim()
    .toLowerCase()
  const map: Record<string, string> = {
    glossary_term: "Term",
    agent: "Agent",
    workflow_run: "Workflow run",
    department: "Department",
    query_cluster: "Topic cluster",
    company: "Company",
    contact: "Contact",
  }
  return map[raw] ?? (raw ? raw.replace(/_/g, " ") : "Item")
}

export function surfaceLabel(value: unknown): string {
  const raw = String(value ?? "")
    .trim()
    .toLowerCase()
  if (!raw) return "—"
  return SURFACE_LABELS[raw] ?? raw.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}

export function stageLabel(value: unknown): string {
  const raw = String(value ?? "")
    .trim()
    .toLowerCase()
  if (!raw) return "?"
  return STAGE_LABELS[raw] ?? raw.replace(/_/g, " ")
}

export function snakeToTitle(value: unknown): string {
  const raw = String(value ?? "")
    .trim()
    .replace(/_/g, " ")
  if (!raw) return "—"
  return raw.replace(/\b\w/g, (c) => c.toUpperCase())
}

export function statusLabel(value: unknown): string {
  const raw = String(value ?? "")
    .trim()
    .toLowerCase()
  const map: Record<string, string> = {
    open: "Open",
    closed: "Closed",
    resolved: "Resolved",
    pending: "Pending",
    candidate: "Needs review",
    approved: "Approved",
    rejected: "Rejected",
    insufficient_data: "Not enough data yet",
    ready: "Ready",
    healthy: "Healthy",
    advisory_only: "Suggestions only — never auto-applied",
  }
  return map[raw] ?? snakeToTitle(raw)
}

export function memoryCategoryLabel(value: unknown): string {
  const raw = String(value ?? "")
    .trim()
    .toLowerCase()
  const map: Record<string, string> = {
    preference: "Preference",
    fact: "Fact",
    procedure: "Procedure",
    glossary: "Glossary",
    policy: "Policy",
    contact: "Contact",
    memory: "Memory",
  }
  return map[raw] ?? snakeToTitle(raw)
}
