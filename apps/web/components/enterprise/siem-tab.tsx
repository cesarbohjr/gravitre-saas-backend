"use client"

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
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
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
  )
}
