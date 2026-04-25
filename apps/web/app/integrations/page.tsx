"use client"

import { useState } from "react"
import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { StatusBadge } from "@/components/gravitre/status-badge"
import { EnvironmentBadge } from "@/components/gravitre/environment-badge"
import { Button } from "@/components/ui/button"
import { Plus, AlertCircle, RefreshCw } from "lucide-react"

interface Integration {
  id: string
  name: string
  type: "slack" | "email" | "webhook"
  status: "active" | "inactive" | "error"
  environment: "production" | "staging"
  lastUpdated: string
}

const integrations: Integration[] = [
  {
    id: "int-001",
    name: "Slack Notifications",
    type: "slack",
    status: "active",
    environment: "production",
    lastUpdated: "2 hours ago",
  },
  {
    id: "int-002",
    name: "Email Alerts",
    type: "email",
    status: "active",
    environment: "production",
    lastUpdated: "1 day ago",
  },
  {
    id: "int-003",
    name: "External API Webhook",
    type: "webhook",
    status: "error",
    environment: "staging",
    lastUpdated: "5 minutes ago",
  },
  {
    id: "int-004",
    name: "Billing Webhook",
    type: "webhook",
    status: "inactive",
    environment: "production",
    lastUpdated: "3 days ago",
  },
]

const statusVariants: Record<string, "success" | "error" | "muted"> = {
  active: "success",
  inactive: "muted",
  error: "error",
}

const typeLabels: Record<string, string> = {
  slack: "Slack",
  email: "Email",
  webhook: "Webhook",
}

export default function IntegrationsPage() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const isAdmin = true

  // Simulate loading state
  // useEffect(() => { setIsLoading(true); setTimeout(() => setIsLoading(false), 1000); }, [])

  return (
    <AppShell title="Integrations">
      <div className="p-6">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold text-foreground">Integrations</h1>
            <EnvironmentBadge environment="production" />
          </div>
          {isAdmin && (
            <Button size="sm" className="h-8 gap-2" asChild>
              <Link href="/integrations/new">
                <Plus className="h-3.5 w-3.5" />
                New integration
              </Link>
            </Button>
          )}
        </div>

        {/* Error State */}
        {error && (
          <div className="mb-6 flex items-center justify-between rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-destructive" />
              <span className="text-sm text-destructive">{error}</span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 gap-1.5 text-xs"
              onClick={() => setError(null)}
            >
              <RefreshCw className="h-3 w-3" />
              Retry
            </Button>
          </div>
        )}

        {/* Table */}
        <div className="rounded-lg border border-border bg-card">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Name
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Type
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Environment
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Last Updated
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isLoading ? (
                // Loading skeleton
                Array.from({ length: 4 }).map((_, i) => (
                  <tr key={i}>
                    <td className="px-4 py-4">
                      <div className="h-4 w-32 animate-pulse rounded bg-muted" />
                    </td>
                    <td className="px-4 py-4">
                      <div className="h-4 w-16 animate-pulse rounded bg-muted" />
                    </td>
                    <td className="px-4 py-4">
                      <div className="h-5 w-16 animate-pulse rounded bg-muted" />
                    </td>
                    <td className="px-4 py-4">
                      <div className="h-5 w-20 animate-pulse rounded bg-muted" />
                    </td>
                    <td className="px-4 py-4">
                      <div className="h-4 w-24 animate-pulse rounded bg-muted" />
                    </td>
                  </tr>
                ))
              ) : integrations.length === 0 ? (
                // Empty state
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center">
                    <p className="text-sm text-muted-foreground">No integrations found.</p>
                  </td>
                </tr>
              ) : (
                // Data rows
                integrations.map((integration) => (
                  <tr
                    key={integration.id}
                    className="cursor-pointer transition-colors hover:bg-muted/50"
                  >
                    <td className="px-4 py-4">
                      <Link
                        href={`/integrations/${integration.id}`}
                        className="text-sm font-medium text-foreground hover:underline"
                      >
                        {integration.name}
                      </Link>
                    </td>
                    <td className="px-4 py-4">
                      <span className="text-sm text-muted-foreground">
                        {typeLabels[integration.type]}
                      </span>
                    </td>
                    <td className="px-4 py-4">
                      <StatusBadge variant={statusVariants[integration.status]} dot>
                        {integration.status}
                      </StatusBadge>
                    </td>
                    <td className="px-4 py-4">
                      <EnvironmentBadge environment={integration.environment} />
                    </td>
                    <td className="px-4 py-4">
                      <span className="text-sm text-muted-foreground">
                        {integration.lastUpdated}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </AppShell>
  )
}
