"use client"

import { useState } from "react"
import { toast } from "sonner"
import { Building2, ShieldCheck, ArrowRight, ArrowLeft, Check, Loader2 } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"
import { federationApi } from "@/lib/api"

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

const CONSENT_TERMS = [
  "Both organizations must explicitly accept before any data flows.",
  "Agent handoffs and delegated tasks require per-exchange consent.",
  "Connector grants are scoped, time-limited, and revocable at any time.",
  "Either party can revoke the partnership, immediately halting all access.",
]

export function InvitePartnerDialog({
  open,
  onOpenChange,
  onInvited,
  disabled,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onInvited: () => void
  disabled?: boolean
}) {
  const [step, setStep] = useState(0)
  const [orgId, setOrgId] = useState("")
  const [acknowledged, setAcknowledged] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  function reset() {
    setStep(0)
    setOrgId("")
    setAcknowledged(false)
    setSubmitting(false)
  }

  function handleOpenChange(next: boolean) {
    if (!next) reset()
    onOpenChange(next)
  }

  const trimmed = orgId.trim()
  const validUuid = UUID_RE.test(trimmed)
  const canContinue = validUuid

  async function submit() {
    if (!acknowledged || disabled) return
    setSubmitting(true)
    try {
      await federationApi.invitePartner(trimmed)
      toast.success("Partnership invitation sent")
      onInvited()
      handleOpenChange(false)
    } catch (err) {
      toast.error("Could not send the invitation", {
        description: err instanceof Error ? err.message : "Verify the organization ID and try again.",
      })
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-primary" />
            Invite a partner organization
          </DialogTitle>
          <DialogDescription>
            Federation is consent-based. Review the terms before sending an invitation.
          </DialogDescription>
        </DialogHeader>

        {/* Step indicator */}
        <div className="flex items-center gap-2">
          {[0, 1].map((s) => (
            <div key={s} className="flex flex-1 items-center gap-2">
              <div
                className={cn(
                  "flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium transition-colors",
                  step >= s
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground",
                )}
              >
                {step > s ? <Check className="h-3.5 w-3.5" /> : s + 1}
              </div>
              <div
                className={cn(
                  "h-1 flex-1 rounded-full transition-colors",
                  step > s ? "bg-primary" : "bg-muted",
                )}
              />
            </div>
          ))}
        </div>

        {step === 0 && (
          <div className="space-y-3 py-2">
            <Label htmlFor="partner-org">Partner organization ID</Label>
            <div className="relative">
              <Building2 className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="partner-org"
                value={orgId}
                onChange={(e) => setOrgId(e.target.value)}
                placeholder="00000000-0000-0000-0000-000000000000"
                className="pl-9 font-mono"
                autoFocus
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Ask your partner for their organization UUID. They&apos;ll receive an invitation that
              they must accept before the partnership becomes active.
            </p>
            {trimmed.length > 0 && !validUuid ? (
              <p className="text-xs text-destructive">Enter a valid organization UUID.</p>
            ) : null}
          </div>
        )}

        {step === 1 && (
          <div className="space-y-3 py-2">
            <p className="text-sm font-medium">How federation consent works</p>
            <ul className="space-y-2">
              {CONSENT_TERMS.map((term) => (
                <li key={term} className="flex items-start gap-2 text-sm text-muted-foreground">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-chart-1" />
                  <span className="leading-relaxed">{term}</span>
                </li>
              ))}
            </ul>
            <label className="mt-2 flex cursor-pointer items-start gap-2 rounded-lg border border-border bg-muted/30 p-3">
              <input
                type="checkbox"
                checked={acknowledged}
                onChange={(e) => setAcknowledged(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-border accent-primary"
              />
              <span className="text-sm">
                I understand that inviting{" "}
                <span className="font-mono text-foreground">{trimmed}</span> records my
                organization&apos;s consent to federate.
              </span>
            </label>
          </div>
        )}

        <DialogFooter className="gap-2 sm:gap-2">
          {step === 0 ? (
            <Button
              className="gap-1.5"
              disabled={!canContinue || disabled}
              onClick={() => setStep(1)}
            >
              Continue
              <ArrowRight className="h-4 w-4" />
            </Button>
          ) : (
            <>
              <Button variant="outline" className="gap-1.5" onClick={() => setStep(0)}>
                <ArrowLeft className="h-4 w-4" />
                Back
              </Button>
              <Button
                className="gap-1.5"
                disabled={!acknowledged || submitting || disabled}
                onClick={submit}
              >
                {submitting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ShieldCheck className="h-4 w-4" />
                )}
                {submitting ? "Sending…" : "Send invitation"}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
