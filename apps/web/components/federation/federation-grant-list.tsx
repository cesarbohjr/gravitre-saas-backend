"use client"

import { useState } from "react"
import { formatDistanceToNow } from "date-fns"
import { Check, Plug, X } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { FederationConnectorGrant } from "@/types/api"

const STATUS_CLASS: Record<string, string> = {
  pending: "border-amber-500/30 text-amber-600",
  active: "border-emerald-500/30 text-emerald-600",
  rejected: "border-border text-muted-foreground",
  revoked: "border-border text-muted-foreground",
}

export function FederationGrantList({
  grants,
  currentOrgId,
  onAction,
}: {
  grants: FederationConnectorGrant[]
  currentOrgId?: string
  onAction: (action: "accept" | "reject" | "revoke", grant: FederationConnectorGrant) => Promise<void>
}) {
  const [busy, setBusy] = useState<string | null>(null)

  if (grants.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-border/70 px-4 py-8 text-center text-sm text-muted-foreground">
        No connector grants yet. Propose a grant from the API or partner onboarding flow.
      </p>
    )
  }

  async function run(action: "accept" | "reject" | "revoke", grant: FederationConnectorGrant) {
    setBusy(`${grant.id}:${action}`)
    try {
      await onAction(action, grant)
    } finally {
      setBusy(null)
    }
  }

  return (
    <ul className="space-y-3">
      {grants.map((grant) => {
        const isGrantee = currentOrgId === grant.granteeOrgId
        const isGrantor = currentOrgId === grant.grantorOrgId
        const canAccept = isGrantee && grant.status === "pending"
        const canReject = isGrantee && grant.status === "pending"
        const canRevoke = isGrantor && grant.status === "active"
        return (
          <li key={grant.id} className="rounded-xl border border-border/70 bg-card/50 p-4 space-y-2">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <Plug className="h-4 w-4 text-primary shrink-0" />
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">{grant.label || grant.connectorId}</p>
                  <p className="text-xs text-muted-foreground font-mono truncate">{grant.connectorId}</p>
                </div>
              </div>
              <Badge variant="outline" className={cn("capitalize", STATUS_CLASS[grant.status] ?? "")}>
                {grant.status}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              Actions: {(grant.allowedActions ?? []).slice(0, 4).join(", ") || "—"}
              {grant.expiresAt ? (
                <> · expires {formatDistanceToNow(new Date(grant.expiresAt), { addSuffix: true })}</>
              ) : null}
            </p>
            <div className="flex flex-wrap gap-2">
              {canAccept ? (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy !== null}
                  onClick={() => void run("accept", grant)}
                >
                  {busy === `${grant.id}:accept` ? "…" : (
                    <>
                      <Check className="h-3.5 w-3.5 mr-1" />
                      Accept
                    </>
                  )}
                </Button>
              ) : null}
              {canReject ? (
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={busy !== null}
                  onClick={() => void run("reject", grant)}
                >
                  <X className="h-3.5 w-3.5 mr-1" />
                  Decline
                </Button>
              ) : null}
              {canRevoke ? (
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-destructive"
                  disabled={busy !== null}
                  onClick={() => void run("revoke", grant)}
                >
                  Revoke
                </Button>
              ) : null}
            </div>
          </li>
        )
      })}
    </ul>
  )
}
