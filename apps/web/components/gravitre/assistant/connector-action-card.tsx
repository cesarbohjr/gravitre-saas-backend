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
    <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50/80 p-4 shadow-sm">
      <div className="flex items-start gap-2 mb-3">
        <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
        <div>
          <p className="text-sm font-medium text-amber-900">
            {connectors.length} connector{connectors.length !== 1 ? "s" : ""} need authentication
          </p>
          <p className="text-xs text-amber-700 mt-1">
            Complete the OAuth flow for each connector — usually about 30 seconds each.
          </p>
        </div>
      </div>
      <div className="space-y-2">
        {connectors.map((connector) => {
          const slug = (connector.type || connector.name || "").toLowerCase().replace(/\s+/g, "_")
          return (
            <div key={slug} className="flex items-center justify-between gap-3 rounded-lg bg-white/70 px-3 py-2 border border-amber-100">
              <span className="text-sm text-zinc-800 capitalize">{connector.name || connector.type}</span>
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
