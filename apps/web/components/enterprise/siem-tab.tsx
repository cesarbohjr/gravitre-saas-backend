"use client"

<<<<<<< HEAD
import { useEffect, useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import { Shield, KeyRound, Send, Lock, CheckCircle2, XCircle } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Separator } from "@/components/ui/separator"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { cn } from "@/lib/utils"
import { enterpriseApi } from "@/lib/api"
import type { EnterpriseSiemConfig } from "@/types/api"
import { TabSkeleton } from "./enterprise-skeletons"

export function SiemTab({ isAdmin }: { isAdmin: boolean }) {
  const { data, isLoading, mutate } = useSWR<EnterpriseSiemConfig>(
    "enterprise-siem",
    () => enterpriseApi.getSiem(),
    { revalidateOnFocus: false },
  )

  const [enabled, setEnabled] = useState(false)
  const [endpoint, setEndpoint] = useState("")
  const [secret, setSecret] = useState("")
  const [rotating, setRotating] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)

  useEffect(() => {
    if (!data) return
    setEnabled(Boolean(data.enabled))
    setEndpoint(data.endpoint ?? "")
  }, [data])

  if (isLoading) return <TabSkeleton rows={3} />

  const hasSecret = data?.hasSecret ?? false
  const showSecretInput = !hasSecret || rotating

  const handleSave = async () => {
    if (!isAdmin) return
    setSaving(true)
    try {
      const payload: { enabled: boolean; endpoint: string | null; secret?: string | null } = {
        enabled,
        endpoint: endpoint.trim() || null,
      }
      // Only send secret when entering/rotating — blank keeps the existing one.
      if (showSecretInput && secret.trim()) {
        payload.secret = secret.trim()
      }
      const updated = await enterpriseApi.updateSiem(payload)
      await mutate(updated, { revalidate: false })
      setSecret("")
      setRotating(false)
      toast.success("SIEM configuration saved")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save configuration")
=======
import { useState } from "react"
import { Loader2, Save, Shield } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"
import { Skeleton } from "@/components/ui/skeleton"
import { toast } from "sonner"
import { enterpriseApi } from "@/lib/api"

interface SiemTabProps {
  isAdmin: boolean
  isLoading: boolean
  siemEnabled: boolean
  siemEndpoint: string
  siemSecret: string
  hasSecret?: boolean
  onEnabledChange: (v: boolean) => void
  onEndpointChange: (v: string) => void
  onSecretChange: (v: string) => void
  onSaved: () => Promise<void>
}

export function SiemTab({
  isAdmin,
  isLoading,
  siemEnabled,
  siemEndpoint,
  siemSecret,
  hasSecret,
  onEnabledChange,
  onEndpointChange,
  onSecretChange,
  onSaved,
}: SiemTabProps) {
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    if (!isAdmin) return
    if (!siemEndpoint) {
      toast.error("Endpoint is required")
      return
    }
    if (!siemSecret && !hasSecret) {
      toast.error("Signing secret is required")
      return
    }
    setSaving(true)
    try {
      await enterpriseApi.updateSiemConfig({
        endpoint: siemEndpoint,
        secret: siemSecret || undefined,
        enabled: siemEnabled,
      })
      toast.success("SIEM configuration saved")
      onSecretChange("")
      await onSaved()
    } catch {
      toast.error("Failed to save SIEM configuration")
>>>>>>> eac2b609fbbcbbd202990b3258ff11c9e2f0003c
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
<<<<<<< HEAD
    setTesting(true)
    try {
      const result = await enterpriseApi.testSiem()
      if (result.ok) {
        toast.success("Test event delivered successfully")
      } else {
        toast.error(result.message || `Delivery failed${result.status ? ` (${result.status})` : ""}`)
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Test delivery failed")
    } finally {
      setTesting(false)
    }
  }

  return (
    <div className="space-y-4">
      <Card className="border-l-2 border-l-primary">
        <CardHeader>
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/10">
              <Shield className="h-4 w-4 text-primary" />
            </span>
            <div>
              <CardTitle className="text-base">SIEM event forwarding</CardTitle>
              <CardDescription className="mt-0.5">
                Stream audit and security events to your SIEM via webhook.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between gap-4">
            <div className="space-y-0.5">
              <Label htmlFor="siem-enabled">Enable forwarding</Label>
              <p className="text-xs text-muted-foreground">
                When on, security events are delivered to the endpoint below.
              </p>
            </div>
            <Switch
              id="siem-enabled"
              checked={enabled}
              onCheckedChange={setEnabled}
              disabled={!isAdmin}
            />
          </div>

          <Separator />

          <div className="space-y-2">
            <Label htmlFor="siem-endpoint">Endpoint URL</Label>
            <Input
              id="siem-endpoint"
              type="url"
              placeholder="https://siem.yourcompany.com/ingest"
              value={endpoint}
              onChange={(e) => setEndpoint(e.target.value)}
              disabled={!isAdmin}
              className="font-mono text-sm"
            />
          </div>

          {/* Secret — security-forward, muted red accent */}
          <div className="space-y-2">
            <Label htmlFor="siem-secret" className="flex items-center gap-1.5">
              <KeyRound className="h-3.5 w-3.5 text-destructive" />
              Signing secret
            </Label>

            {hasSecret && !rotating ? (
              <div className="flex items-center justify-between gap-2 rounded-md border border-border bg-secondary/40 px-3 py-2">
                <div className="flex items-center gap-2">
                  <Lock className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="font-mono text-sm text-muted-foreground">
                    {"•".repeat(20)}
                  </span>
                  <Badge variant="secondary" className="text-[10px]">
                    Configured
                  </Badge>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 text-xs text-destructive hover:text-destructive"
                  onClick={() => setRotating(true)}
                  disabled={!isAdmin}
                >
                  Rotate
                </Button>
              </div>
            ) : (
              <>
                <Input
                  id="siem-secret"
                  type="password"
                  placeholder={hasSecret ? "Enter new secret to rotate" : "Enter signing secret"}
                  value={secret}
                  onChange={(e) => setSecret(e.target.value)}
                  disabled={!isAdmin}
                  className="font-mono text-sm"
                  autoComplete="off"
                />
                {rotating && (
                  <button
                    type="button"
                    onClick={() => {
                      setRotating(false)
                      setSecret("")
                    }}
                    className="text-xs text-muted-foreground hover:text-foreground"
                  >
                    Cancel rotation
                  </button>
                )}
              </>
            )}
            <p className="text-xs text-muted-foreground">
              Used to HMAC-sign delivered payloads. Leaving this blank keeps the existing secret.
            </p>
          </div>

          {!isAdmin && (
            <Alert>
              <Lock className="h-4 w-4" />
              <AlertTitle>Read-only</AlertTitle>
              <AlertDescription>
                Only organization admins can configure SIEM forwarding.
              </AlertDescription>
            </Alert>
          )}

          {isAdmin && (
            <div className="flex flex-col items-stretch gap-2 sm:flex-row sm:items-center sm:justify-between">
              <Button
                variant="outline"
                onClick={handleTest}
                disabled={testing || !endpoint.trim()}
                className="gap-1.5"
              >
                <Send className={cn("h-3.5 w-3.5", testing && "animate-pulse")} />
                {testing ? "Sending…" : "Send test event"}
              </Button>
              <Button onClick={handleSave} disabled={saving} className="gap-1.5">
                {saving ? "Saving…" : "Save configuration"}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Delivery status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-sm">
            {enabled && (data?.endpoint || endpoint) ? (
              <>
                <CheckCircle2 className="h-4 w-4 text-success" />
                <span className="text-foreground">Forwarding active</span>
                <span className="text-muted-foreground">— events stream to your endpoint</span>
              </>
            ) : (
              <>
                <XCircle className="h-4 w-4 text-muted-foreground" />
                <span className="text-muted-foreground">
                  Forwarding inactive — enable and set an endpoint to begin
                </span>
              </>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
=======
    if (!isAdmin || !siemEndpoint || !siemSecret) {
      toast.error("Enter endpoint and secret to test")
      return
    }
    setSaving(true)
    try {
      const result = await enterpriseApi.testSiem({ endpoint: siemEndpoint, secret: siemSecret })
      if (result.delivered) toast.success("Test event delivered")
      else toast.error(result.error || "Delivery failed")
    } catch {
      toast.error("SIEM test failed")
    } finally {
      setSaving(false)
    }
  }

  if (isLoading) {
    return <Skeleton className="h-64 w-full" />
  }

  return (
    <Card className="border-red-500/10">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Shield className="h-4 w-4 text-red-400" />
          SIEM export
        </CardTitle>
        <CardDescription>
          Stream redacted audit events to Splunk, Datadog, or any HMAC-verified webhook.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between rounded-lg border border-border bg-secondary/20 p-3">
          <div>
            <p className="text-sm font-medium">Enable export</p>
            <p className="text-xs text-muted-foreground">Audit events dispatch asynchronously</p>
          </div>
          <Switch checked={siemEnabled} disabled={!isAdmin} onCheckedChange={onEnabledChange} />
        </div>
        <div>
          <Label htmlFor="siem-endpoint">Webhook endpoint</Label>
          <Input
            id="siem-endpoint"
            value={siemEndpoint}
            disabled={!isAdmin}
            onChange={(e) => onEndpointChange(e.target.value)}
            placeholder="https://..."
            className="mt-1"
          />
        </div>
        <div>
          <Label htmlFor="siem-secret" className="text-red-400/90">
            Signing secret
          </Label>
          <Input
            id="siem-secret"
            type="password"
            value={siemSecret}
            disabled={!isAdmin}
            onChange={(e) => onSecretChange(e.target.value)}
            placeholder={hasSecret ? "Leave blank to keep existing secret" : "Required"}
            className="mt-1 border-red-500/20 focus-visible:ring-red-500/30"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" className="gap-2" disabled={!isAdmin || saving} onClick={handleSave}>
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
            Save SIEM
          </Button>
          <Button size="sm" variant="outline" disabled={!isAdmin || saving} onClick={handleTest}>
            Send test event
          </Button>
        </div>
      </CardContent>
    </Card>
>>>>>>> eac2b609fbbcbbd202990b3258ff11c9e2f0003c
  )
}
