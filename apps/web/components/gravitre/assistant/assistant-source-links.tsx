"use client"

import Link from "next/link"
import type { ToolInvocation } from "@/components/gravitre/assistant/tool-chip"

function connectorNeedsAuth(result: unknown): boolean {
  if (!result || typeof result !== "object") return false
  const connectors = (result as { connectors?: unknown[] }).connectors
  if (!Array.isArray(connectors)) return false
  return connectors.some((row) => {
    if (!row || typeof row !== "object") return false
    const record = row as { blocking_reason?: string; status?: string }
    return (
      record.blocking_reason === "pending_auth" ||
      record.blocking_reason === "token_expired" ||
      record.status === "pending_auth"
    )
  })
}

type Citation = { title: string; href: string; snippet?: string }

function knowledgeCitations(result: unknown): Citation[] {
  if (!result || typeof result !== "object") return []
  const data = result as {
    results?: unknown[]
    sources?: unknown[]
  }
  const rows = Array.isArray(data.results)
    ? data.results
    : Array.isArray(data.sources)
      ? data.sources
      : []
  const citations: Citation[] = []
  for (const row of rows) {
    if (!row || typeof row !== "object") continue
    const record = row as {
      title?: string
      sourceId?: string
      url?: string
      snippet?: string
      excerpt?: string
    }
    const title = String(record.title || "Knowledge source").trim() || "Knowledge source"
    const sourceId = String(record.sourceId || "").trim()
    const url = String(record.url || "").trim()
    const href = sourceId ? `/sources/${sourceId}` : url || ""
    if (!href) continue
    citations.push({
      title,
      href,
      snippet: String(record.snippet || record.excerpt || "").trim() || undefined,
    })
  }
  return citations.slice(0, 5)
}

export function AssistantSourceLinks({ invocations }: { invocations: ToolInvocation[] }) {
  if (!invocations.length) return null

  const links: Array<{ label: string; href: string }> = []
  const citations: Citation[] = []
  const seen = new Set<string>()

  const add = (label: string, href: string) => {
    const key = `${label}:${href}`
    if (seen.has(key)) return
    seen.add(key)
    links.push({ label, href })
  }

  for (const invocation of invocations) {
    if (invocation.state !== "result") continue
    switch (invocation.toolName) {
      case "searchKnowledgeBase": {
        const found = knowledgeCitations(invocation.result)
        if (found.length) {
          citations.push(...found)
        } else {
          add("Sources checked", "/sources")
        }
        break
      }
      case "getConnectorStatus":
        add("Connector status", "/connectors")
        if (connectorNeedsAuth(invocation.result)) {
          add("Fix authentication", "/connectors")
        }
        break
      case "getAnalytics":
        add("Org analytics", "/analytics")
        break
      case "getWorkflowRuns":
        add("Workflow runs", "/workflows")
        break
      case "searchWeb":
        add("Web sources", "#why-this-answer")
        break
      default:
        break
    }
  }

  add("View audit trail", "/audit")
  add("How Gravitre keeps you in control", "/ai/help/control")

  if (!links.length && !citations.length) return null

  return (
    <div className="not-prose mt-3 space-y-2 text-xs text-muted-foreground">
      {citations.length ? (
        <div className="space-y-1.5">
          <div className="font-medium text-foreground/80">Sources checked</div>
          <ol className="list-decimal space-y-1 pl-4">
            {citations.map((citation) => (
              <li key={`${citation.href}:${citation.title}`} className="leading-snug">
                <Link
                  href={citation.href}
                  className="text-foreground underline-offset-2 hover:underline"
                >
                  {citation.title}
                </Link>
                {citation.snippet ? (
                  <span className="mt-0.5 block text-[11px] text-muted-foreground line-clamp-2">
                    {citation.snippet}
                  </span>
                ) : null}
              </li>
            ))}
          </ol>
        </div>
      ) : null}
      {links.length ? (
        <div className="flex flex-wrap items-center gap-x-1 gap-y-1">
          {links.map((link, index) => (
            <span key={link.href + link.label} className="inline-flex items-center">
              {index > 0 ? <span className="mx-1 text-border">·</span> : null}
              <Link href={link.href} className="underline-offset-2 hover:text-foreground hover:underline">
                {link.label}
              </Link>
            </span>
          ))}
        </div>
      ) : null}
    </div>
  )
}
