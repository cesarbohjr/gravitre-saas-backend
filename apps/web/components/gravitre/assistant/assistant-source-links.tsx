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

export function AssistantSourceLinks({ invocations }: { invocations: ToolInvocation[] }) {
  if (!invocations.length) return null

  const links: Array<{ label: string; href: string }> = []
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
      case "searchKnowledgeBase":
        add("Sources checked", "/sources")
        break
      case "getConnectorStatus":
        add("Connector status", "/connectors")
        if (connectorNeedsAuth(invocation.result)) {
          add("Fix authentication", "/connectors")
        }
        break
      case "getAnalytics":
        add("Org analytics", "/metrics")
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

  if (!links.length) return null

  return (
    <div className="not-prose mt-3 flex flex-wrap items-center gap-x-1 gap-y-1 text-xs text-muted-foreground">
      {links.map((link, index) => (
        <span key={link.href + link.label} className="inline-flex items-center">
          {index > 0 ? <span className="mx-1 text-border">·</span> : null}
          <Link href={link.href} className="underline-offset-2 hover:text-foreground hover:underline">
            {link.label}
          </Link>
        </span>
      ))}
    </div>
  )
}
