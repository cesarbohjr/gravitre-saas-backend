"use client"

import { useState } from "react"
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

  if (isLoading) return <TabSkeleton rows={3} />
  if (!data) return null

  return (
    <SiemTabForm
      key={`${data.enabled}-${data.endpoint ?? ""}-${data.hasSecret ?? false}`}
      isAdmin={isAdmin}
      data={data}
      mutate={mutate}
    />
  )
}

function SiemTabForm({
  isAdmin,
  data,
  mutate,
}: {
  isAdmin: boolean
  data: EnterpriseSiemConfig
  mutate: ReturnType<typeof useSWR<EnterpriseSiemConfig>>["mutate"]
}) {
  const [enabled, setEnabled] = useState(Boolean(data.enabled))
  const [endpoint, setEndpoint] = useState(data.endpoint ?? "")
  const [secret, setSecret] = useState("")
  const [rotating, setRotating] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)

  const hasSecret = data.hasSecret ?? false
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
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
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
            {enabled && (data.endpoint || endpoint) ? (
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
  )
}
