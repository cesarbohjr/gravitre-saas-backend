"use client"

import Link from "next/link"
import { AlertTriangle } from "lucide-react"
import { Button } from "@/components/ui/button"

export function ConnectorActionCard({
  connectors,
}: {
  connectors: { name?: string; type?: string; status?: string }[]
}) {
  if (!connectors.length) return null

  return (
    <div className="mt-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 shadow-sm">
      <div className="mb-3 flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
        <div>
          <p className="text-sm font-medium text-amber-950 dark:text-amber-100">
            {connectors.length} connector{connectors.length !== 1 ? "s" : ""} need authentication
          </p>
          <p className="mt-1 text-xs text-amber-800 dark:text-amber-200">
            Complete the OAuth flow for each connector — usually about 30 seconds each.
          </p>
        </div>
      </div>
      <div className="space-y-2">
        {connectors.map((connector) => {
          const slug = (connector.type || connector.name || "").toLowerCase().replace(/\s+/g, "_")
          return (
            <div key={slug} className="flex items-center justify-between gap-3 rounded-lg border border-amber-500/20 bg-background/60 px-3 py-2">
              <span className="text-sm capitalize text-foreground">{connector.name || connector.type}</span>
              <Button asChild variant="outline" size="sm" className="h-7 text-xs">
                <Link href={`/connectors?connect=${encodeURIComponent(slug)}`}>Reconnect →</Link>
              </Button>
            </div>
          )
        })}
      </div>
      <Button asChild variant="link" className="mt-3 h-auto p-0 text-xs text-amber-800">
        <Link href="/connectors?status=pending_auth">Fix all connectors →</Link>
      </Button>
    </div>
  )
}
