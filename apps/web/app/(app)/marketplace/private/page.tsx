"use client"

import { useRef, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
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

const STATUS_VARIANT: Record<
  string,
  "success" | "error" | "warning" | "muted"
> = {
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
  const lock = useRef(false)
  const [failure, setFailure] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [actionId, setActionId] = useState<string | null>(null)

  const { data, error, mutate, isLoading } = useSWR<{
    bundles: PrivateConnectorBundle[]
  }>(user ? "/api/marketplace/private-bundles" : null, fetcher)

  const handleUpload = async () => {
    if (lock.current || !user) return
    let manifest: Record<string, unknown>
    try {
      manifest = JSON.parse(manifestText) as Record<string, unknown>
      if (!manifest || Array.isArray(manifest) || typeof manifest !== "object")
        throw new Error("Manifest must be a JSON object")
    } catch {
      toast.error("Invalid manifest JSON")
      return
    }
    if (!publicKeyPem.trim() || !signature.trim()) {
      toast.error("Public key and signature are required")
      return
    }

    lock.current = true
    setFailure(null)
    setIsUploading(true)
    try {
      await marketplaceApi.uploadPrivateBundle({
        name: name.trim() || "Private connector",
        manifest,
        packageSources: { "handlers.py": handlersSource },
        signingPublicKeyPem: publicKeyPem.trim(),
        signature: signature.trim(),
      })
      toast.success("Private bundle uploaded", {
        description: "Activate when ready (admin).",
      })
      await Promise.allSettled([mutate()])
    } catch (err) {
      setFailure(
        err instanceof Error
          ? err.message
          : "The request failed. Your inputs are retained for retry.",
      )
    } finally {
      lock.current = false
      setIsUploading(false)
    }
  }

  const runBundleAction = async (
    bundleId: string,
    action: "activate" | "disable",
  ) => {
    if (lock.current || !isAdmin) return
    lock.current = true
    setActionId(bundleId)
    try {
      if (action === "activate") {
        await marketplaceApi.activatePrivateBundle(bundleId)
        toast.success("Bundle activated", {
          description: "The server accepted activation for your organization.",
        })
      } else {
        await marketplaceApi.disablePrivateBundle(bundleId)
        toast.success("Bundle disabled")
      }
      await Promise.allSettled([mutate()])
    } catch (err) {
      toast.error("Action failed", {
        description: err instanceof Error ? err.message : "Try again",
      })
    } finally {
      lock.current = false
      setActionId(null)
    }
  }

  const bundles = data?.bundles ?? []

  return (
    <AppShell title="Private connectors">
      <div
        className="bg-[color:var(--g-canvas)] pb-24 [&_[data-slot=button]]:min-h-11 [&_input]:min-h-11"
        data-composition="operate"
      >
        <GravitrePageHeader
          eyebrow="Enterprise · org-scoped"
          title="Private connector runtime"
          description="Upload a signed bundle, inspect its reported status and activate it for your organization when ready."
          icon={<Lock className="h-5 w-5" />}
          actions={
            <Button variant="outline" size="sm" asChild>
              <Link href="/connectors">
                <ArrowLeft className="h-3.5 w-3.5 mr-1.5" />
                Connectors
              </Link>
            </Button>
          }
        />

        <div className="mx-auto max-w-4xl space-y-8 px-[var(--np-page-pad-sm)] py-4 sm:px-[var(--np-page-pad)] sm:py-5">
          <section className="border-y border-border py-5 space-y-4">
            <fieldset
              disabled={isUploading || Boolean(actionId)}
              className="min-w-0 space-y-4"
            >
              <h2 className="text-sm font-medium">Upload signed bundle</h2>
              <label htmlFor="private-name" className="text-sm">
                Bundle name
              </label>
              <Input
                id="private-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Display name"
              />
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
              <label htmlFor="private-signature" className="text-sm">
                Bundle signature
              </label>
              <Input
                id="private-signature"
                value={signature}
                onChange={(e) => setSignature(e.target.value)}
                placeholder="Base64 Ed25519 signature"
              />
              {failure ? (
                <p role="alert" className="text-sm text-destructive">
                  {failure}
                </p>
              ) : null}
              <Button
                onClick={() => void handleUpload()}
                disabled={isUploading}
              >
                {isUploading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  "Upload bundle"
                )}
              </Button>
            </fieldset>
          </section>

          <section className="rounded-lg border border-border bg-card overflow-hidden">
            <div className="px-5 py-3 border-b border-border">
              <h2 className="text-sm font-medium">Your org bundles</h2>
            </div>
            {error ? (
              <WorkSectionErrorCard
                title="Could not refresh private bundles"
                onRetry={() => void mutate()}
              />
            ) : null}
            {isLoading && !data && (
              <p className="px-5 py-6 text-sm text-muted-foreground">
                Loading...
              </p>
            )}
            {data && !isLoading && bundles.length === 0 && (
              <p className="px-5 py-6 text-sm text-muted-foreground">
                No private bundles yet.
              </p>
            )}
            <ul className="divide-y divide-border">
              {bundles.map((bundle) => (
                <li
                  key={bundle.id}
                  className="px-5 py-4 flex flex-col sm:flex-row sm:items-center gap-3"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="font-medium">{bundle.name}</p>
                      <StatusBadge
                        variant={STATUS_VARIANT[bundle.status] ?? "muted"}
                      >
                        {bundle.status}
                      </StatusBadge>
                      {bundle.runtime && (
                        <span className="text-xs text-muted-foreground">
                          runtime: {bundle.runtime}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      {bundle.vendor} · v{bundle.version} · cert{" "}
                      {bundle.certificationStatus ?? "—"}
                    </p>
                  </div>
                  {isAdmin && (
                    <div className="flex gap-2">
                      {bundle.status !== "active" && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="gap-1.5"
                          disabled={Boolean(actionId) || isUploading}
                          onClick={() =>
                            void runBundleAction(bundle.id, "activate")
                          }
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
                          disabled={Boolean(actionId) || isUploading}
                          onClick={() =>
                            void runBundleAction(bundle.id, "disable")
                          }
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
      </div>
    </AppShell>
  )
}
