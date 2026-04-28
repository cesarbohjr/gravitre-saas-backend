"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { AppShell } from "@/components/gravitre/app-shell"
import { EnvironmentBadge } from "@/components/gravitre/environment-badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ArrowLeft, Plus, AlertCircle } from "lucide-react"

type IntegrationType = "slack" | "email" | "webhook"

export default function NewIntegrationPage() {
  const router = useRouter()
  const isAdmin = true

  const [name, setName] = useState("")
  const [type, setType] = useState<IntegrationType | "">("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Webhook-specific fields
  const [allowedHosts, setAllowedHosts] = useState("")
  const [defaultPath, setDefaultPath] = useState("/webhook")
  const [timeout, setTimeout] = useState("30")
  const [maxPayload, setMaxPayload] = useState("1048576")
  const [retryCount, setRetryCount] = useState("3")
  const [retryBackoff, setRetryBackoff] = useState("1000")

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name || !type) {
      setError("Please fill in all required fields")
      return
    }

    setIsSubmitting(true)
    setError(null)

    try {
      // Simulate API call
      await new Promise<void>((resolve) => window.setTimeout(() => resolve(), 1000))
      router.push("/integrations")
    } catch {
      setError("Failed to create integration")
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!isAdmin) {
    return (
      <AppShell title="New Integration">
        <div className="p-6">
          <Link
            href="/integrations"
            className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Integrations
          </Link>

          <div className="rounded-lg border border-border bg-card p-8 text-center">
            <p className="text-sm text-muted-foreground">
              You do not have permission to create integrations.
            </p>
            <p className="mt-2 text-xs text-muted-foreground">
              Contact an administrator to request access.
            </p>
          </div>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell title="New Integration">
      <div className="p-6">
        {/* Header */}
        <div className="mb-6">
          <Link
            href="/integrations"
            className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Integrations
          </Link>

          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold text-foreground">New Integration</h1>
            <EnvironmentBadge environment="production" />
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="max-w-xl">
          <div className="rounded-lg border border-border bg-card">
            <div className="border-b border-border px-4 py-3">
              <h2 className="text-sm font-semibold text-foreground">Integration Details</h2>
            </div>
            <div className="p-4 space-y-4">
              {/* Name */}
              <div>
                <label className="mb-1.5 block text-sm text-muted-foreground">
                  Name <span className="text-destructive">*</span>
                </label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g., Slack Notifications"
                  className="h-9"
                />
              </div>

              {/* Type */}
              <div>
                <label className="mb-1.5 block text-sm text-muted-foreground">
                  Type <span className="text-destructive">*</span>
                </label>
                <Select value={type} onValueChange={(v) => setType(v as IntegrationType)}>
                  <SelectTrigger className="h-9">
                    <SelectValue placeholder="Select integration type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="slack">Slack</SelectItem>
                    <SelectItem value="email">Email</SelectItem>
                    <SelectItem value="webhook">Webhook</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Webhook-specific fields */}
              {type === "webhook" && (
                <>
                  <div className="pt-2 border-t border-border">
                    <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Webhook Configuration
                    </h3>
                  </div>

                  <div>
                    <label className="mb-1.5 block text-sm text-muted-foreground">
                      Allowed Hosts
                    </label>
                    <Input
                      value={allowedHosts}
                      onChange={(e) => setAllowedHosts(e.target.value)}
                      placeholder="e.g., api.example.com, *.internal.com"
                      className="h-9"
                    />
                    <p className="mt-1 text-xs text-muted-foreground">
                      Comma-separated list of allowed hosts
                    </p>
                  </div>

                  <div>
                    <label className="mb-1.5 block text-sm text-muted-foreground">
                      Default Path
                    </label>
                    <Input
                      value={defaultPath}
                      onChange={(e) => setDefaultPath(e.target.value)}
                      placeholder="/webhook"
                      className="h-9 font-mono"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="mb-1.5 block text-sm text-muted-foreground">
                        Timeout (ms)
                      </label>
                      <Input
                        type="number"
                        value={timeout}
                        onChange={(e) => setTimeout(e.target.value)}
                        className="h-9"
                      />
                    </div>
                    <div>
                      <label className="mb-1.5 block text-sm text-muted-foreground">
                        Max Payload (bytes)
                      </label>
                      <Input
                        type="number"
                        value={maxPayload}
                        onChange={(e) => setMaxPayload(e.target.value)}
                        className="h-9"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="mb-1.5 block text-sm text-muted-foreground">
                        Retry Count
                      </label>
                      <Input
                        type="number"
                        value={retryCount}
                        onChange={(e) => setRetryCount(e.target.value)}
                        className="h-9"
                      />
                    </div>
                    <div>
                      <label className="mb-1.5 block text-sm text-muted-foreground">
                        Retry Backoff (ms)
                      </label>
                      <Input
                        type="number"
                        value={retryBackoff}
                        onChange={(e) => setRetryBackoff(e.target.value)}
                        className="h-9"
                      />
                    </div>
                  </div>
                </>
              )}

              {/* Error */}
              {error && (
                <div className="flex items-center gap-2 text-sm text-destructive">
                  <AlertCircle className="h-4 w-4" />
                  {error}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="border-t border-border px-4 py-3 flex justify-end gap-2">
              <Button variant="outline" size="sm" asChild>
                <Link href="/integrations">Cancel</Link>
              </Button>
              <Button
                type="submit"
                size="sm"
                className="gap-2"
                disabled={isSubmitting}
              >
                <Plus className="h-3.5 w-3.5" />
                {isSubmitting ? "Creating..." : "Create integration"}
              </Button>
            </div>
          </div>
        </form>
      </div>
    </AppShell>
  )
}
