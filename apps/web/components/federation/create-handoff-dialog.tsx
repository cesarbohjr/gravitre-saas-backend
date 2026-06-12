"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import {
  ArrowLeft,
  ArrowLeftRight,
  ArrowRight,
  Bot,
  Building2,
  Check,
  Loader2,
  ShieldCheck,
} from "lucide-react"
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
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"
import { agentsApi, federationApi } from "@/lib/api"
import type { FederationPartnership } from "@/types/api"

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

const CONSENT_TERMS = [
  "The partner organization must accept this handoff before any briefing is shared.",
  "Only send context your organization is authorized to exchange under the active partnership.",
  "The receiver can decline the handoff without executing downstream agent work.",
]

export function CreateHandoffDialog({
  open,
  onOpenChange,
  onCreated,
  disabled,
  activePartnerships,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: () => void
  disabled?: boolean
  activePartnerships: FederationPartnership[]
}) {
  const [step, setStep] = useState(0)
  const [receiverOrgId, setReceiverOrgId] = useState("")
  const [fromAgentId, setFromAgentId] = useState("")
  const [toAgentId, setToAgentId] = useState("")
  const [title, setTitle] = useState("")
  const [message, setMessage] = useState("")
  const [acknowledged, setAcknowledged] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const { data: agentsData, isLoading: loadingAgents } = useSWR(
    open ? "federation/create-handoff/agents" : null,
    () => agentsApi.list(),
  )

  const agents = useMemo(() => agentsData?.agents ?? [], [agentsData])

  function reset() {
    setStep(0)
    setReceiverOrgId("")
    setFromAgentId("")
    setToAgentId("")
    setTitle("")
    setMessage("")
    setAcknowledged(false)
    setSubmitting(false)
  }

  function handleOpenChange(next: boolean) {
    if (!next) reset()
    onOpenChange(next)
  }

  const trimmedToAgent = toAgentId.trim()
  const validToAgent = trimmedToAgent.length === 0 || UUID_RE.test(trimmedToAgent)
  const trimmedTitle = title.trim()
  const trimmedMessage = message.trim()
  const canContinue =
    Boolean(receiverOrgId) &&
    validToAgent &&
    (trimmedTitle.length > 0 || trimmedMessage.length > 0)

  async function submit() {
    if (!acknowledged || disabled || !receiverOrgId) return
    setSubmitting(true)
    try {
      await federationApi.createHandoff({
        receiverOrgId,
        fromAgentId: fromAgentId || undefined,
        toAgentId: trimmedToAgent || undefined,
        message: trimmedMessage || undefined,
        briefing: {
          ...(trimmedTitle ? { title: trimmedTitle } : {}),
          ...(trimmedMessage
            ? { decision: { summary: trimmedMessage } }
            : {}),
        },
      })
      toast.success("Cross-org handoff sent", {
        description: "Your partner must accept before the briefing is actionable.",
      })
      onCreated()
      handleOpenChange(false)
    } catch (err) {
      toast.error("Could not send handoff", {
        description: err instanceof Error ? err.message : "Verify the partnership and try again.",
      })
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ArrowLeftRight className="h-5 w-5 text-primary" />
            Send cross-org handoff
          </DialogTitle>
          <DialogDescription>
            Exchange a structured agent briefing with an active partner organization.
          </DialogDescription>
        </DialogHeader>

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
          <div className="space-y-4 py-2">
            {activePartnerships.length === 0 ? (
              <p className="rounded-lg border border-border bg-muted/30 p-3 text-sm text-muted-foreground">
                You need at least one active partnership before sending a handoff. Invite a partner
                and wait for mutual consent.
              </p>
            ) : (
              <>
                <div className="space-y-2">
                  <Label htmlFor="handoff-partner">Partner organization</Label>
                  <Select value={receiverOrgId} onValueChange={setReceiverOrgId}>
                    <SelectTrigger id="handoff-partner" className="w-full">
                      <SelectValue placeholder="Select an active partner" />
                    </SelectTrigger>
                    <SelectContent>
                      {activePartnerships.map((partnership) => (
                        <SelectItem key={partnership.id} value={partnership.partnerOrgId}>
                          <span className="flex items-center gap-2">
                            <Building2 className="h-3.5 w-3.5 text-muted-foreground" />
                            <span className="font-mono text-xs">{partnership.partnerOrgId}</span>
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="handoff-from-agent">From agent (optional)</Label>
                    <Select
                      value={fromAgentId || "__none__"}
                      onValueChange={(value) => setFromAgentId(value === "__none__" ? "" : value)}
                      disabled={loadingAgents}
                    >
                      <SelectTrigger id="handoff-from-agent" className="w-full">
                        <SelectValue placeholder={loadingAgents ? "Loading agents…" : "Your agent"} />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__none__">No specific agent</SelectItem>
                        {agents.map((agent) => (
                          <SelectItem key={agent.id} value={agent.id}>
                            <span className="flex items-center gap-2">
                              <Bot className="h-3.5 w-3.5 text-muted-foreground" />
                              {agent.name}
                            </span>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="handoff-to-agent">To agent (optional)</Label>
                    <Input
                      id="handoff-to-agent"
                      value={toAgentId}
                      onChange={(e) => setToAgentId(e.target.value)}
                      placeholder="Partner agent UUID"
                      className="font-mono text-xs"
                    />
                    {trimmedToAgent.length > 0 && !validToAgent ? (
                      <p className="text-xs text-destructive">Enter a valid agent UUID or leave blank.</p>
                    ) : null}
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="handoff-title">Briefing title</Label>
                  <Input
                    id="handoff-title"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="e.g. Escalated renewal review"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="handoff-message">Context for partner agents</Label>
                  <Textarea
                    id="handoff-message"
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    placeholder="Summarize what the partner org should know or decide next."
                    rows={4}
                  />
                  <p className="text-xs text-muted-foreground">
                    Provide a title or context message so the receiver knows why this handoff was sent.
                  </p>
                </div>
              </>
            )}
          </div>
        )}

        {step === 1 && (
          <div className="space-y-3 py-2">
            <p className="text-sm font-medium">Consent before exchange</p>
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
                I authorize sending this briefing to partner org{" "}
                <span className="font-mono text-foreground">{receiverOrgId}</span>.
              </span>
            </label>
          </div>
        )}

        <DialogFooter className="gap-2 sm:gap-2">
          {step === 0 ? (
            <Button
              className="gap-1.5"
              disabled={!canContinue || disabled || activePartnerships.length === 0}
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
                {submitting ? "Sending…" : "Send handoff"}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
