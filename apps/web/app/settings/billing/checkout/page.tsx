"use client"

import { Suspense, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { loadStripe } from "@stripe/stripe-js"
import { Elements, PaymentElement, useElements, useStripe } from "@stripe/react-stripe-js"
import { ArrowLeft, Loader2, Shield } from "lucide-react"
import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { billingApi, ApiRequestError } from "@/lib/api"
import { getPlan, formatPlanPrice, type PlanCode } from "@/lib/plans"
import { toast } from "sonner"

const stripePublishableKey = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY ?? ""
const stripePromise = stripePublishableKey ? loadStripe(stripePublishableKey) : null

type CheckoutFormProps = {
  planCode: PlanCode
  billingInterval: "monthly" | "annual"
  returnUrl: string
}

function CheckoutForm({ planCode, billingInterval, returnUrl }: CheckoutFormProps) {
  const stripe = useStripe()
  const elements = useElements()
  const router = useRouter()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [elementReady, setElementReady] = useState(false)
  const plan = getPlan(planCode)

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
            <p className="text-2xl font-bold text-primary">{formatPlanPrice(plan)}</p>
            {plan.price !== null && plan.price > 0 && (
              <p className="text-xs text-muted-foreground">/month</p>
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
  const planCode = parsePlanCode(searchParams.get("plan"))
  const billingInterval = parseBillingInterval(searchParams.get("interval"))
  const [clientSecret, setClientSecret] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    if (!planCode) return

    let cancelled = false
    void (async () => {
      try {
        const response = await billingApi.createSubscriptionForPlan(planCode, billingInterval)
        if (!cancelled) {
          setClientSecret(response.client_secret)
        }
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
  }, [planCode, billingInterval])

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
            <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
              {loadError}
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
                appearance: {
                  theme: "stripe",
                  variables: {
                    borderRadius: "8px",
                  },
                },
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
