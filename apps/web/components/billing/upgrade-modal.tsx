"use client"

import Link from "next/link"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"

const PLANS = [
  { code: "node", name: "Node", price: "$49/mo", highlights: ["1 core user", "10 workflows", "Essential connectors"] },
  { code: "control", name: "Control", price: "$129/mo", highlights: ["5 lite seats", "Meson builder", "Advanced connectors"] },
  { code: "command", name: "Command", price: "$299/mo", highlights: ["25 lite seats", "SSO & API access", "Unlimited workflows"] },
]

interface UpgradeModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  subscriptionStatus?: string
}

export function UpgradeModal({ open, onOpenChange, subscriptionStatus }: UpgradeModalProps) {
  const title =
    subscriptionStatus === "trial_expired"
      ? "Your trial has ended"
      : subscriptionStatus === "past_due"
        ? "Payment required"
        : "Choose a plan"

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            Select Node, Control, or Command to restore full access. Checkout uses your existing Stripe billing flow.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-3 md:grid-cols-3">
          {PLANS.map((plan) => (
            <div key={plan.code} className="rounded-lg border border-border p-4">
              <p className="font-semibold text-foreground">{plan.name}</p>
              <p className="text-lg font-semibold text-primary">{plan.price}</p>
              <ul className="mt-3 space-y-1 text-xs text-muted-foreground">
                {plan.highlights.map((item) => (
                  <li key={item}>• {item}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Not now
          </Button>
          <Button asChild>
            <Link href="/settings/billing">Continue to billing</Link>
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
