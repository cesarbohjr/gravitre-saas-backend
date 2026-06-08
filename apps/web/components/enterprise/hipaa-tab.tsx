"use client"

import { useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import {
  HeartPulse,
  ShieldCheck,
  ShieldAlert,
  Lock,
  FileCheck,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { cn } from "@/lib/utils"
import { enterpriseApi } from "@/lib/api"
import type { EnterpriseHipaaStatus } from "@/types/api"
import { TabSkeleton } from "./enterprise-skeletons"

export function HipaaTab({ isAdmin }: { isAdmin: boolean }) {
  const { data, isLoading, mutate } = useSWR<EnterpriseHipaaStatus>(
    "enterprise-hipaa",
    () => enterpriseApi.getHipaa(),
    { revalidateOnFocus: false },
  )

  const [baaDialogOpen, setBaaDialogOpen] = useState(false)
  const [accepting, setAccepting] = useState(false)
  const [toggling, setToggling] = useState(false)

  if (isLoading) return <TabSkeleton rows={3} />
  if (!data) return null

  const usRegion = data.dataRegion === "us"
  const canEnable = data.baaAccepted && usRegion

  const handleAcceptBaa = async () => {
    if (!isAdmin) return
    setAccepting(true)
    try {
      const updated = await enterpriseApi.acceptHipaaBaa({ baaVersion: data.requiredBaaVersion })
      await mutate(updated, { revalidate: false })
      toast.success("Business Associate Agreement accepted")
      setBaaDialogOpen(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to accept BAA")
    } finally {
      setAccepting(false)
    }
  }

  const handleToggleHipaa = async (enabled: boolean) => {
    if (!isAdmin) return
    setToggling(true)
    try {
      const updated = await enterpriseApi.updateHipaa({ enabled })
      await mutate(updated, { revalidate: false })
      toast.success(enabled ? "HIPAA mode enabled" : "HIPAA mode disabled")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update HIPAA mode")
    } finally {
      setToggling(false)
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <HeartPulse className="h-4 w-4 text-primary" />
              <CardTitle className="text-base">HIPAA compliance</CardTitle>
            </div>
            <Badge
              variant={data.hipaaReady ? "default" : "secondary"}
              className={cn("gap-1", data.hipaaReady && "bg-success text-success-foreground")}
            >
              {data.hipaaReady ? (
                <>
                  <ShieldCheck className="h-3 w-3" /> HIPAA ready
                </>
              ) : (
                <>
                  <ShieldAlert className="h-3 w-3" /> Restricted
                </>
              )}
            </Badge>
          </div>
          <CardDescription>
            Accept the BAA, enable HIPAA mode, and use US data residency before PHI-capable connectors or
            sensitive outbound tools are allowed.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid gap-3 sm:grid-cols-3">
            <StatusTile
              label="BAA"
              ok={data.baaAccepted}
              detail={
                data.baaAccepted
                  ? `Version ${data.baaVersion ?? data.requiredBaaVersion}`
                  : `Required: ${data.requiredBaaVersion}`
              }
            />
            <StatusTile
              label="Data region"
              ok={usRegion}
              detail={usRegion ? "United States" : `${(data.dataRegion ?? "unknown").toUpperCase()} — US required`}
            />
            <StatusTile
              label="PHI connectors"
              ok={data.phiCapableConnectorCount === 0 || data.hipaaReady}
              detail={`${data.phiCapableConnectorCount} tagged`}
            />
          </div>

          {!data.baaAccepted && (
            <Alert>
              <FileCheck className="h-4 w-4" />
              <AlertTitle>Business Associate Agreement required</AlertTitle>
              <AlertDescription className="space-y-3">
                <span className="block">
                  Before handling PHI, an organization admin must accept the current BAA (
                  {data.requiredBaaVersion}).
                </span>
                {isAdmin ? (
                  <Button size="sm" onClick={() => setBaaDialogOpen(true)}>
                    Review and accept BAA
                  </Button>
                ) : (
                  <span className="block text-muted-foreground">Contact your workspace admin to accept.</span>
                )}
              </AlertDescription>
            </Alert>
          )}

          {data.baaAccepted && !usRegion && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>US data residency required</AlertTitle>
              <AlertDescription>
                HIPAA mode requires the organization data region to be United States. Change it under Data
                Residency before enabling HIPAA mode.
              </AlertDescription>
            </Alert>
          )}

          <div className="flex items-center justify-between rounded-lg border border-border p-4">
            <div className="space-y-1">
              <Label htmlFor="hipaa-mode" className="text-sm font-medium">
                HIPAA mode
              </Label>
              <p className="text-xs text-muted-foreground">
                When enabled with an accepted BAA in US region, PHI-capable connectors and blocked tools become
                available.
              </p>
            </div>
            <Switch
              id="hipaa-mode"
              checked={data.enabled}
              disabled={!isAdmin || toggling || (!data.enabled && !canEnable)}
              onCheckedChange={handleToggleHipaa}
            />
          </div>

          {!data.hipaaReady && data.blockedActionsWhenInactive.length > 0 && (
            <div className="space-y-2">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Blocked until HIPAA ready
              </span>
              <div className="flex flex-wrap gap-2">
                {data.blockedActionsWhenInactive.map((action) => (
                  <code
                    key={action}
                    className="rounded-md border border-border bg-secondary/50 px-2 py-1 font-mono text-xs"
                  >
                    {action}
                  </code>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">
                Tools using connectors marked PHI-capable are also blocked until HIPAA mode is active.
              </p>
            </div>
          )}

          {data.baaAcceptedAt && (
            <p className="text-xs text-muted-foreground">
              BAA accepted {new Date(data.baaAcceptedAt).toLocaleString()}
              {data.baaAcceptedBy ? ` · user ${data.baaAcceptedBy.slice(0, 8)}…` : ""}
            </p>
          )}

          {!isAdmin && (
            <Alert>
              <Lock className="h-4 w-4" />
              <AlertTitle>Read-only</AlertTitle>
              <AlertDescription>
                Only organization admins can accept the BAA or toggle HIPAA mode.
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      <Dialog open={baaDialogOpen} onOpenChange={setBaaDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Accept Business Associate Agreement</DialogTitle>
            <DialogDescription className="space-y-2 pt-1">
              <span className="block">
                By accepting version <strong className="text-foreground">{data.requiredBaaVersion}</strong>,
                you confirm your organization will use Gravitre in compliance with HIPAA requirements for
                protected health information.
              </span>
              <span className="block">
                You must also enable HIPAA mode and maintain US data residency before PHI workflows run.
              </span>
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setBaaDialogOpen(false)} disabled={accepting}>
              Cancel
            </Button>
            <Button onClick={handleAcceptBaa} disabled={accepting}>
              {accepting ? "Accepting…" : "I accept the BAA"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function StatusTile({ label, ok, detail }: { label: string; ok: boolean; detail: string }) {
  return (
    <div className="rounded-lg border border-border p-3">
      <div className="flex items-center gap-2">
        {ok ? (
          <CheckCircle2 className="h-4 w-4 text-success" />
        ) : (
          <AlertTriangle className="h-4 w-4 text-amber-500" />
        )}
        <span className="text-sm font-medium text-foreground">{label}</span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
    </div>
  )
}
