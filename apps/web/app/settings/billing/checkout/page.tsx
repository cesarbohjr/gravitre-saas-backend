"use client"

import { Suspense, useCallback, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { useTheme } from "next-themes"
import { loadStripe, type Appearance } from "@stripe/stripe-js"
import { Elements, PaymentElement, useElements, useStripe } from "@stripe/react-stripe-js"
import { ArrowLeft, Loader2, RefreshCw, Shield } from "lucide-react"
import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { ApiRequestError } from "@/lib/api"
import { startPlanCheckout } from "@/lib/billing-checkout"
import {
  getPlan,
  formatPlanPrice,
  annualBilledTotal,
  type BillingInterval,
  type PlanCode,
} from "@/lib/plans"
import { toast } from "sonner"

const stripePublishableKey = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY ?? ""
const stripePromise = stripePublishableKey ? loadStripe(stripePublishableKey) : null

type CheckoutFormProps = {
  planCode: PlanCode
  billingInterval: BillingInterval
  returnUrl: string
}

function CheckoutForm({ planCode, billingInterval, returnUrl }: CheckoutFormProps) {
  const stripe = useStripe()
  const elements = useElements()
  const router = useRouter()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [elementReady, setElementReady] = useState(false)
  const plan = getPlan(planCode)
  const isAnnual = billingInterval === "annual"
  const priceLabel = formatPlanPrice(plan, billingInterval)
  const isPaidPlan = plan.price !== null && plan.price > 0
  const annualTotal = annualBilledTotal(plan)

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!stripe || !elements) return

    setIsSubmitting(true)
    const { error } = await stripe.confirmPayment({
      elements,
      confirmParams: { return_url: returnUrl },
    })

    if (error) {
      toast.error(error.message ?? "Payment failed. Please try again.")
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6" data-testid="payment-element-form">
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <p className="text-sm text-muted-foreground">Subscribe to</p>
            <p className="text-xl font-semibold text-foreground">{plan.name}</p>
            <p className="text-sm text-muted-foreground capitalize">{billingInterval} billing</p>
          </div>
          <div className="text-right">
            <p className="text-2xl font-bold text-primary">{priceLabel}</p>
            {isPaidPlan && <p className="text-xs text-muted-foreground">/month</p>}
            {isPaidPlan && isAnnual && annualTotal !== null && (
              <p className="mt-0.5 text-xs text-muted-foreground">Billed annually · ${annualTotal}/yr</p>
            )}
          </div>
        </div>
        <PaymentElement onReady={() => setElementReady(true)} options={{ layout: "tabs" }} />
      </div>

      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Shield className="h-3.5 w-3.5 shrink-0" />
        Payments are processed securely by Stripe. Your card is saved for renewals.
      </div>

      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
        <Button
          type="button"
          variant="outline"
          onClick={() => router.push("/settings/billing")}
          disabled={isSubmitting}
        >
          Cancel
        </Button>
        <Button
          type="submit"
          disabled={!stripe || !elements || !elementReady || isSubmitting}
          data-testid="payment-element-submit"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Processing…
            </>
          ) : (
            `Subscribe to ${plan.name}`
          )}
        </Button>
      </div>
    </form>
  )
}

function parsePlanCode(value: string | null): PlanCode | null {
  if (value === "node" || value === "control" || value === "command") {
    return value
  }
  return null
}

function parseBillingInterval(value: string | null): "monthly" | "annual" {
  if (value === "annual" || value === "year" || value === "yearly") {
    return "annual"
  }
  return "monthly"
}

export default function BillingCheckoutPage() {
  return (
    <Suspense
      fallback={
        <AppShell>
          <div className="flex items-center justify-center gap-2 py-24 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
            Loading checkout…
          </div>
        </AppShell>
      }
    >
      <BillingCheckoutPageInner />
    </Suspense>
  )
}

function BillingCheckoutPageInner() {
  const searchParams = useSearchParams()
  const { resolvedTheme } = useTheme()
  const planCode = parsePlanCode(searchParams.get("plan"))
  const billingInterval = parseBillingInterval(searchParams.get("interval"))
  const [clientSecret, setClientSecret] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  const handleRetry = useCallback(() => {
    setLoadError(null)
    setClientSecret(null)
    setReloadKey((key) => key + 1)
  }, [])

  useEffect(() => {
    if (!planCode) return

    let cancelled = false
    void (async () => {
      try {
        const result = await startPlanCheckout(planCode, billingInterval)
        if (cancelled) return

        if (result.mode === "redirect") {
          window.location.assign(result.url)
          return
        }

        setClientSecret(result.clientSecret)
      } catch (error) {
        if (!cancelled) {
          const message =
            error instanceof ApiRequestError
              ? error.message
              : error instanceof Error
                ? error.message
                : "Could not start checkout"
          setLoadError(message)
        }
      }
    })()

    return () => {
      cancelled = true
    }
  }, [planCode, billingInterval, reloadKey])

  // Match the Stripe Payment Element to the app's active light/dark theme and
  // brand corner radius so it doesn't render as a light card on a dark page.
  const stripeAppearance: Appearance = {
    theme: resolvedTheme === "dark" ? "night" : "stripe",
    variables: { borderRadius: "8px" },
  }

  const returnUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}/settings/billing?status=success`
      : "/settings/billing?status=success"

  if (!planCode) {
    return (
      <AppShell>
        <div className="mx-auto max-w-lg px-6 py-16 text-center">
          <p className="text-muted-foreground">Select a plan to continue.</p>
          <Button asChild className="mt-4">
            <Link href="/settings/billing">View plans</Link>
          </Button>
        </div>
      </AppShell>
    )
  }

  const plan = getPlan(planCode)

  return (
    <AppShell>
      <div className="relative flex-1 overflow-auto">
        <div className="mx-auto max-w-lg px-6 py-10">
          <Link
            href="/settings/billing"
            className="mb-6 inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to billing
          </Link>

          <div className="mb-8">
            <h1 className="text-2xl font-bold text-foreground">Complete your subscription</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Enter payment details to activate {plan.name} and restore full access.
            </p>
          </div>

          {!stripePublishableKey && (
            <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
              Stripe is not configured. Set NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY in your environment.
            </div>
          )}

          {loadError && (
            <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-4">
              <p className="text-sm text-destructive">{loadError}</p>
              <Button variant="outline" size="sm" onClick={handleRetry} className="mt-3">
                <RefreshCw className="h-3.5 w-3.5" />
                Try again
              </Button>
            </div>
          )}

          {!clientSecret && !loadError && stripePublishableKey && (
            <div className="flex items-center justify-center gap-2 py-16 text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin" />
              Preparing checkout…
            </div>
          )}

          {clientSecret && stripePromise && (
            <Elements
              stripe={stripePromise}
              options={{
                clientSecret,
                appearance: stripeAppearance,
              }}
            >
              <CheckoutForm planCode={planCode} billingInterval={billingInterval} returnUrl={returnUrl} />
            </Elements>
          )}
        </div>
      </div>
    </AppShell>
  )
}
