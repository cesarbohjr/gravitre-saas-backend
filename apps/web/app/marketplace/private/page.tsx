"use client"

import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { StatusBadge } from "@/components/gravitre/status-badge"
import { marketplaceApi } from "@/lib/api"
import { fetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { ArrowLeft, Loader2, Lock, Play, Square } from "lucide-react"
import { toast } from "sonner"
import type { PrivateConnectorBundle } from "@/types/api"

const STATUS_VARIANT: Record<string, "success" | "error" | "warning" | "muted"> = {
  draft: "warning",
  active: "success",
  disabled: "muted",
}

const DEFAULT_MANIFEST = `{
  "manifestVersion": "1.0",
  "id": "com.example.internal",
  "name": "Internal Connector",
  "version": "1.0.0",
  "vendor": "internal_tools",
  "auth": { "type": "apiKey", "headerName": "X-Api-Key" },
  "capabilities": ["actions"],
  "actions": [
    {
      "id": "items.list",
      "name": "List items",
      "scopes": ["internal_tools:items:read"]
    }
  ]
}`

const DEFAULT_HANDLERS = `def items_list(ctx, params):
    return {
        "success": True,
        "action": "internal_tools.items.list",
        "data": {"items": [], "private": True},
    }
`

export default function MarketplacePrivatePage() {
  const { user } = useAuth()
  const { isAdmin } = useOrgAdmin()
  const [name, setName] = useState("Internal Connector")
  const [manifestText, setManifestText] = useState(DEFAULT_MANIFEST)
  const [handlersSource, setHandlersSource] = useState(DEFAULT_HANDLERS)
  const [publicKeyPem, setPublicKeyPem] = useState("")
  const [signature, setSignature] = useState("")
  const [isUploading, setIsUploading] = useState(false)
  const [actionId, setActionId] = useState<string | null>(null)

  const { data, mutate, isLoading } = useSWR<{ bundles: PrivateConnectorBundle[] }>(
    user ? "/api/marketplace/private-bundles" : null,
    fetcher
  )

  const handleUpload = async () => {
    let manifest: Record<string, unknown>
    try {
      manifest = JSON.parse(manifestText) as Record<string, unknown>
    } catch {
      toast.error("Invalid manifest JSON")
      return
    }
    if (!publicKeyPem.trim() || !signature.trim()) {
      toast.error("Public key and signature are required")
      return
    }

    setIsUploading(true)
    try {
      await marketplaceApi.uploadPrivateBundle({
        name: name.trim() || "Private connector",
        manifest,
        packageSources: { "handlers.py": handlersSource },
        signingPublicKeyPem: publicKeyPem.trim(),
        signature: signature.trim(),
      })
      toast.success("Private bundle uploaded", { description: "Activate when ready (admin)." })
      await mutate()
    } catch (err) {
      toast.error("Upload failed", {
        description: err instanceof Error ? err.message : "Check signature and security scan",
      })
    } finally {
      setIsUploading(false)
    }
  }

  const runBundleAction = async (bundleId: string, action: "activate" | "disable") => {
    setActionId(bundleId)
    try {
      if (action === "activate") {
        await marketplaceApi.activatePrivateBundle(bundleId)
        toast.success("Bundle activated", { description: "Runs in isolated sandbox via invoke_tool" })
      } else {
        await marketplaceApi.disablePrivateBundle(bundleId)
        toast.success("Bundle disabled")
      }
      await mutate()
    } catch (err) {
      toast.error("Action failed", { description: err instanceof Error ? err.message : "Try again" })
    } finally {
      setActionId(null)
    }
  }

  const bundles = data?.bundles ?? []

  return (
    <AppShell title="Private connectors">
      <div className="mx-auto max-w-4xl p-6 space-y-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
              <Lock className="h-4 w-4" />
              Enterprise · org-scoped
            </div>
            <h1 className="text-2xl font-semibold">Private connector runtime</h1>
            <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
              Upload signed connector bundles that run in an isolated worker sandbox. See{" "}
              <code className="text-xs bg-secondary px-1 rounded">docs/integration/private-connector-runtime.md</code>.
            </p>
          </div>
          <Button variant="outline" size="sm" asChild>
            <Link href="/connectors">
              <ArrowLeft className="h-3.5 w-3.5 mr-1.5" />
              Connectors
            </Link>
          </Button>
        </div>

        <section className="rounded-lg border border-border bg-card p-5 space-y-4">
          <h2 className="text-sm font-medium">Upload signed bundle</h2>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Display name" />
          <Textarea
            value={manifestText}
            onChange={(e) => setManifestText(e.target.value)}
            className="font-mono text-xs min-h-[200px] bg-secondary/40"
            spellCheck={false}
          />
          <Textarea
            value={handlersSource}
            onChange={(e) => setHandlersSource(e.target.value)}
            className="font-mono text-xs min-h-[140px] bg-secondary/40"
            spellCheck={false}
          />
          <Textarea
            value={publicKeyPem}
            onChange={(e) => setPublicKeyPem(e.target.value)}
            placeholder="-----BEGIN PUBLIC KEY-----"
            className="font-mono text-xs min-h-[100px] bg-secondary/40"
            spellCheck={false}
          />
          <Input
            value={signature}
            onChange={(e) => setSignature(e.target.value)}
            placeholder="Base64 Ed25519 signature"
          />
          <Button onClick={() => void handleUpload()} disabled={isUploading}>
            {isUploading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Upload bundle"}
          </Button>
        </section>

        <section className="rounded-lg border border-border bg-card overflow-hidden">
          <div className="px-5 py-3 border-b border-border">
            <h2 className="text-sm font-medium">Your org bundles</h2>
          </div>
          {isLoading && <p className="px-5 py-6 text-sm text-muted-foreground">Loading...</p>}
          {!isLoading && bundles.length === 0 && (
            <p className="px-5 py-6 text-sm text-muted-foreground">No private bundles yet.</p>
          )}
          <ul className="divide-y divide-border">
            {bundles.map((bundle) => (
              <li key={bundle.id} className="px-5 py-4 flex flex-col sm:flex-row sm:items-center gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="font-medium">{bundle.name}</p>
                    <StatusBadge variant={STATUS_VARIANT[bundle.status] ?? "muted"}>{bundle.status}</StatusBadge>
                    {bundle.runtime && (
                      <span className="text-xs text-muted-foreground">runtime: {bundle.runtime}</span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    {bundle.vendor} · v{bundle.version} · cert {bundle.certificationStatus ?? "—"}
                  </p>
                </div>
                {isAdmin && (
                  <div className="flex gap-2">
                    {bundle.status !== "active" && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="gap-1.5"
                        disabled={actionId === bundle.id}
                        onClick={() => void runBundleAction(bundle.id, "activate")}
                      >
                        {actionId === bundle.id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Play className="h-3.5 w-3.5" />
                        )}
                        Activate
                      </Button>
                    )}
                    {bundle.status === "active" && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="gap-1.5"
                        disabled={actionId === bundle.id}
                        onClick={() => void runBundleAction(bundle.id, "disable")}
                      >
                        <Square className="h-3.5 w-3.5" />
                        Disable
                      </Button>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </section>
      </div>
    </AppShell>
  )
}
