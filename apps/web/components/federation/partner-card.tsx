"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import {
  Building2,
  Check,
  X,
  ShieldOff,
  Clock,
  CheckCircle2,
  ArrowRight,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { StatusBeacon } from "@/components/gravitre/premium-effects"
import { cn } from "@/lib/utils"
import { getSelectedOrgFromStorage } from "@/lib/org-context"
import type { FederationPartnership, FederationPartnershipStatus } from "@/types/api"

const STATUS_META: Record<
  FederationPartnershipStatus,
  { label: string; tone: string; beacon: "active" | "processing" | "warning" | "error" | "idle" }
> = {
  active: { label: "Active", tone: "text-chart-1 border-chart-1/30 bg-chart-1/10", beacon: "active" },
  pending_partner: {
    label: "Pending consent",
    tone: "text-chart-3 border-chart-3/30 bg-chart-3/10",
    beacon: "warning",
  },
  rejected: { label: "Declined", tone: "text-muted-foreground border-border bg-muted/40", beacon: "idle" },
  revoked: { label: "Revoked", tone: "text-destructive border-destructive/30 bg-destructive/10", beacon: "error" },
}

function shortOrg(id: string) {
  if (!id) return "Unknown org"
  return `Org ${id.slice(0, 8)}`
}

function formatDate(value: string | null) {
  if (!value) return null
  try {
    return new Date(value).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    })
  } catch {
    return null
  }
}

function viewerOrgId(partnership: FederationPartnership) {
  return partnership.currentOrgId || getSelectedOrgFromStorage()?.id || ""
}

function awaitingOurConsent(partnership: FederationPartnership) {
  const orgId = viewerOrgId(partnership)
  if (!orgId) return false
  return (
    partnership.status === "pending_partner" &&
    partnership.invitedByOrgId !== orgId
  )
}

export function PartnerCard({
  partnership,
  onAction,
}: {
  partnership: FederationPartnership
  onAction: (
    action: "accept" | "reject" | "revoke",
    partnership: FederationPartnership,
  ) => Promise<void>
}) {
  const [busy, setBusy] = useState<string | null>(null)
  const meta = STATUS_META[partnership.status]
  const needsOurConsent = awaitingOurConsent(partnership)
  const weInvited = partnership.invitedByOrgId === viewerOrgId(partnership)

  async function run(action: "accept" | "reject" | "revoke") {
    setBusy(action)
    try {
      await onAction(action, partnership)
    } finally {
      setBusy(null)
    }
  }

  const consentSteps = [
    { label: "Initiator", done: Boolean(partnership.initiatorConsentAt) },
    { label: "Partner", done: Boolean(partnership.partnerConsentAt) },
  ]

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8, scale: 0.98 }}
      transition={{ type: "spring", stiffness: 360, damping: 30 }}
      whileHover={{ y: -3 }}
      className={cn(
        "group relative overflow-hidden rounded-xl border bg-card p-5 transition-colors",
        partnership.status === "active"
          ? "border-chart-1/30 hover:border-chart-1/50"
          : "border-border hover:border-border/80",
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-muted text-foreground">
            <Building2 className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p className="truncate font-medium">{shortOrg(partnership.partnerOrgId)}</p>
              <StatusBeacon status={meta.beacon} />
            </div>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {weInvited ? "You invited this organization" : "Invited your organization"}
            </p>
          </div>
        </div>
        <Badge variant="outline" className={cn("shrink-0 text-[11px]", meta.tone)}>
          {meta.label}
        </Badge>
      </div>

      {/* Mutual consent progress */}
      <div className="mt-4 flex items-center gap-2">
        {consentSteps.map((step, i) => (
          <div key={step.label} className="flex items-center gap-2">
            <motion.div
              animate={step.done ? { scale: [1, 1.08, 1] } : {}}
              transition={{ duration: 0.4 }}
              className={cn(
                "flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium",
                step.done
                  ? "border-chart-1/30 bg-chart-1/10 text-chart-1"
                  : "border-border bg-muted/40 text-muted-foreground",
              )}
            >
              {step.done ? (
                <CheckCircle2 className="h-3 w-3" />
              ) : (
                <Clock className="h-3 w-3" />
              )}
              {step.label}
            </motion.div>
            {i === 0 && <ArrowRight className="h-3 w-3 text-muted-foreground/50" />}
          </div>
        ))}
        {partnership.createdAt && (
          <span className="ml-auto text-[11px] text-muted-foreground">
            {formatDate(partnership.createdAt)}
          </span>
        )}
      </div>

      {/* Actions */}
      <div className="mt-4 flex flex-wrap gap-2">
        {needsOurConsent && (
          <>
            <Button
              size="sm"
              className="h-8 gap-1.5"
              disabled={busy !== null}
              onClick={() => run("accept")}
            >
              <Check className="h-3.5 w-3.5" />
              {busy === "accept" ? "Accepting…" : "Accept"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-8 gap-1.5"
              disabled={busy !== null}
              onClick={() => run("reject")}
            >
              <X className="h-3.5 w-3.5" />
              Decline
            </Button>
          </>
        )}
        {partnership.status === "active" && (
          <Button
            size="sm"
            variant="ghost"
            className="h-8 gap-1.5 text-destructive hover:bg-destructive/10 hover:text-destructive"
            disabled={busy !== null}
            onClick={() => run("revoke")}
          >
            <ShieldOff className="h-3.5 w-3.5" />
            {busy === "revoke" ? "Revoking…" : "Revoke access"}
          </Button>
        )}
        {partnership.status === "pending_partner" && !needsOurConsent && (
          <p className="text-xs text-muted-foreground">Waiting for partner to accept your invitation.</p>
        )}
      </div>
    </motion.div>
  )
}

export { awaitingOurConsent }
