"use client"

import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { AdaptiveDataView } from "@/components/gravitre/adaptive-data-view"
import { Button } from "@/components/ui/button"
import { marketplaceApi } from "@/lib/api"
import { fetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { setSelectedOrgInStorage } from "@/lib/org-context"
import { FlaskConical, Loader2, ArrowRight, RefreshCw, ArrowLeft, Play } from "lucide-react"
import { toast } from "sonner"
import type { MarketplaceSandboxDemoResult, MarketplaceSandboxStatus } from "@/types/api"

export default function MarketplaceSandboxPage() {
  const { user } = useAuth()
  const [isWorking, setIsWorking] = useState(false)
  const [demoResult, setDemoResult] = useState<MarketplaceSandboxDemoResult | null>(null)

  const { data, mutate, isLoading } = useSWR<MarketplaceSandboxStatus>(
    user ? "/api/marketplace/sandbox" : null,
    fetcher
  )

  const handleProvision = async () => {
    setIsWorking(true)
    try {
      const result = await marketplaceApi.provisionSandbox()
      toast.success(result.created ? "Sandbox created" : "Sandbox ready", {
        description: result.sandboxOrgName,
      })
      await mutate()
    } catch (err) {
      toast.error("Could not provision sandbox", {
        description: err instanceof Error ? err.message : "Try again",
      })
    } finally {
      setIsWorking(false)
    }
  }

  const handleReset = async () => {
    setIsWorking(true)
    try {
      await marketplaceApi.resetSandbox()
      toast.success("Sandbox reset", { description: "Demo agents and connectors re-seeded." })
      await mutate()
    } catch (err) {
      toast.error("Reset failed", { description: err instanceof Error ? err.message : "Try again" })
    } finally {
      setIsWorking(false)
    }
  }

  const handleRunDemo = async () => {
    setIsWorking(true)
    try {
      const result = await marketplaceApi.runSandboxDemo()
      setDemoResult(result)
      if (result.success) {
        toast.success("Marketplace demo completed", {
          description: `${result.tickets.length} ticket(s) from ${result.action}`,
        })
      } else {
        toast.error("Demo invoke failed", {
          description: result.errorMessage ?? "Check connector and agent permissions.",
        })
      }
    } catch (err) {
      toast.error("Could not run demo", {
        description: err instanceof Error ? err.message : "Try again",
      })
    } finally {
      setIsWorking(false)
    }
  }

  const openSandbox = () => {
    if (!data?.sandboxOrgId || !data.sandboxOrgName) return
    setSelectedOrgInStorage({ id: data.sandboxOrgId, name: data.sandboxOrgName })
    toast.success("Switched to sandbox org", { description: data.sandboxOrgName })
    window.location.assign("/connectors")
  }

  return (
    <AppShell title="Partner sandbox">
      <div className="mx-auto max-w-2xl p-6 space-y-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
              <FlaskConical className="h-4 w-4" />
              Marketplace · Sandbox
            </div>
            <h1 className="text-2xl font-semibold">Partner connector sandbox</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Isolated org with demo agents, Acme Tools mock connector, and a smoke-test workflow for partner QA.
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" asChild>
              <Link href="/marketplace/billing">Billing</Link>
            </Button>
            <Button variant="outline" size="sm" asChild>
              <Link href="/marketplace/submit">
                <ArrowLeft className="h-3.5 w-3.5 mr-1.5" />
                Submit
              </Link>
            </Button>
          </div>
        </div>

        {isLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading sandbox status...
          </div>
        ) : data?.provisioned ? (
          <div className="rounded-lg border border-border bg-card p-5 space-y-4">
            <div>
              <p className="text-sm font-medium">{data.sandboxOrgName}</p>
              <p className="text-xs text-muted-foreground mt-1">Org ID: {data.sandboxOrgId}</p>
              {data.seededAt && (
                <p className="text-xs text-muted-foreground">Last seeded: {new Date(data.seededAt).toLocaleString()}</p>
              )}
            </div>
            <p className="text-sm text-muted-foreground">{data.welcomeMessage}</p>
            <ul className="text-xs text-muted-foreground list-disc pl-4 space-y-1">
              <li>Integration QA Agent with Acme Tools permissions</li>
              <li>Pre-connected Acme Tools connector (demo API key)</li>
              <li>Partner connector smoke test workflow</li>
            </ul>
            <div className="flex flex-wrap gap-2 pt-2">
              <Button onClick={openSandbox} className="gap-2">
                Open sandbox
                <ArrowRight className="h-4 w-4" />
              </Button>
              <Button
                variant="secondary"
                onClick={() => void handleRunDemo()}
                disabled={isWorking}
                className="gap-2"
              >
                {isWorking ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                Run marketplace demo
              </Button>
              <Button variant="outline" onClick={() => void handleReset()} disabled={isWorking} className="gap-2">
                {isWorking ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                Reset demo data
              </Button>
            </div>

            {demoResult && (
              <div className="rounded-md border border-border bg-muted/30 p-4 space-y-4 mt-2">
                <div>
                  <p className="text-sm font-medium">
                    {demoResult.success ? "Demo invoke succeeded" : "Demo invoke failed"}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {demoResult.agentName} → {demoResult.connectorName} · {demoResult.action}
                  </p>
                </div>

                {demoResult.success && demoResult.tickets.length > 0 && (
                  <ul className="text-xs space-y-1">
                    {demoResult.tickets.map((ticket) => (
                      <li key={String(ticket.id)} className="text-muted-foreground">
                        #{String(ticket.id)} — {String(ticket.subject ?? "Ticket")}
                      </li>
                    ))}
                  </ul>
                )}

                {demoResult.auditTrail.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Audit trail</p>
                    <AdaptiveDataView className="rounded border border-border">
                      <table className="w-full text-xs">
                        <thead className="bg-muted/50">
                          <tr>
                            <th className="text-left px-3 py-2 font-medium">Action</th>
                            <th className="text-left px-3 py-2 font-medium">Time</th>
                          </tr>
                        </thead>
                        <tbody>
                          {demoResult.auditTrail.map((entry) => (
                            <tr key={entry.id} className="border-t border-border">
                              <td className="px-3 py-2 font-mono">{entry.action}</td>
                              <td className="px-3 py-2 text-muted-foreground">
                                {entry.createdAt ? new Date(entry.createdAt).toLocaleString() : "—"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </AdaptiveDataView>
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-border bg-card/50 p-8 text-center space-y-4">
            <p className="text-sm text-muted-foreground">
              No sandbox yet for this workspace. Provisioning creates a separate org — your production data stays untouched.
            </p>
            <Button onClick={() => void handleProvision()} disabled={isWorking} className="gap-2">
              {isWorking ? <Loader2 className="h-4 w-4 animate-spin" /> : <FlaskConical className="h-4 w-4" />}
              Provision partner sandbox
            </Button>
          </div>
        )}
      </div>
    </AppShell>
  )
}
