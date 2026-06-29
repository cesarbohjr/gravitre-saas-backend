"use client"

import { useState } from "react"
import { Check, Loader2 } from "lucide-react"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { billingApi } from "@/lib/api"
import { SELECTABLE_PLANS, formatPlanPrice } from "@/lib/plans"
import { cn } from "@/lib/utils"
import { toast } from "sonner"

interface UpgradeModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  subscriptionStatus?: string
}

export function UpgradeModal({ open, onOpenChange, subscriptionStatus }: UpgradeModalProps) {
  // Default to the recommended middle tier so the primary action is never stuck.
  const [selectedPlan, setSelectedPlan] = useState<string>("control")
  const [isProcessing, setIsProcessing] = useState(false)

  const title =
    subscriptionStatus === "trial_expired"
      ? "Your trial has ended"
      : subscriptionStatus === "past_due"
        ? "Payment required"
        : "Choose a plan"

  const handleContinue = async () => {
    setIsProcessing(true)
    try {
      const response = await billingApi.createCheckoutForPlan(selectedPlan, "monthly")
      if (response.checkout_url) {
        window.location.assign(response.checkout_url)
        return
      }
      toast.error("Could not start checkout. Please try again.")
    } catch (error) {
      console.error("[v0] Upgrade checkout failed:", error)
      toast.error("Failed to start checkout")
    } finally {
      setIsProcessing(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl" data-testid="upgrade-modal">
        <DialogHeader>
          <DialogTitle data-testid="upgrade-modal-title">{title}</DialogTitle>
          <DialogDescription>
            Select Node, Control, or Command to restore full access. Checkout uses your existing Stripe billing flow.
          </DialogDescription>
        </DialogHeader>

        <div role="radiogroup" aria-label="Choose a plan" className="grid gap-3 md:grid-cols-3">
          {SELECTABLE_PLANS.map((plan) => {
            const isSelected = selectedPlan === plan.code
            return (
              <button
                key={plan.code}
                type="button"
                role="radio"
                aria-checked={isSelected}
                data-testid={`upgrade-plan-${plan.code}`}
                onClick={() => setSelectedPlan(plan.code)}
                className={cn(
                  "relative rounded-lg border p-4 text-left transition-all",
                  "hover:border-primary/60 hover:shadow-sm",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                  isSelected ? "border-primary ring-2 ring-primary/20 bg-primary/[0.03]" : "border-border",
                )}
              >
                {plan.popular && (
                  <span className="absolute -top-2 right-3 rounded-full bg-primary px-2 py-0.5 text-[10px] font-medium text-primary-foreground">
                    Most popular
                  </span>
                )}
                <span
                  aria-hidden
                  className={cn(
                    "absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full border transition-colors",
                    isSelected ? "border-primary bg-primary text-primary-foreground" : "border-border bg-background",
                  )}
                >
                  {isSelected && <Check className="h-3 w-3" />}
                </span>
                <p className="font-semibold text-foreground">{plan.name}</p>
                <p className="text-lg font-semibold text-primary">{formatPlanPrice(plan)}/mo</p>
                <ul className="mt-3 space-y-1 text-xs text-muted-foreground">
                  {plan.features.map((item) => (
                    <li key={item}>• {item}</li>
                  ))}
                </ul>
              </button>
            )
          })}
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isProcessing}>
            Not now
          </Button>
          <Button onClick={handleContinue} disabled={isProcessing} data-testid="upgrade-continue-checkout">
            {isProcessing ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Starting checkout…
              </>
            ) : (
              `Continue with ${SELECTABLE_PLANS.find((p) => p.code === selectedPlan)?.name ?? "plan"}`
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
