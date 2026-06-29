"use client"

import { Suspense, useState } from "react"
import { useSearchParams, useRouter } from "next/navigation"
import Link from "next/link"
import { motion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { MorphingBackground, GlowOrb } from "@/components/gravitre/premium-effects"
import { Button } from "@/components/ui/button"
import { ArrowLeft, Check, Lock, ShieldCheck, Loader2, ExternalLink, Sparkles } from "lucide-react"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth-context"
import { billingApi } from "@/lib/api"
import { getPlan, formatPlanPrice, PLAN_CATALOG, type PlanCode } from "@/lib/plans"
import { toast } from "sonner"

function isSelectablePlanCode(code: string | null): code is PlanCode {
  return !!code && code in PLAN_CATALOG && PLAN_CATALOG[code as PlanCode].selectable
}

function CheckoutContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { user } = useAuth()
  const [isRedirecting, setIsRedirecting] = useState(false)

  const planParam = searchParams.get("plan")
  const interval = searchParams.get("interval") === "annual" ? "annual" : "monthly"

  // Honest guard: only real, self-serve plans can be checked out here.
  if (!isSelectablePlanCode(planParam)) {
    return (
      <div className="relative z-10 px-6 py-16 lg:px-8">
        <div className="max-w-md mx-auto text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-secondary">
            <Sparkles className="h-6 w-6 text-muted-foreground" />
          </div>
          <h1 className="text-lg font-semibold text-foreground">Choose a plan to continue</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            We couldn&apos;t find a plan to check out. Pick one from your billing settings to get started.
          </p>
          <Button asChild className="mt-6">
            <Link href="/settings/billing">Back to billing</Link>
          </Button>
        </div>
      </div>
    )
  }

  const plan = getPlan(planParam)
  const PlanIcon = plan.icon
  const priceLabel = formatPlanPrice(plan)

  const handleCheckout = async () => {
    if (!user) {
      toast.error("Sign in required")
      return
    }
    setIsRedirecting(true)
    try {
      const response = await billingApi.createCheckoutForPlan(plan.code, interval)
      if (response.checkout_url) {
        window.location.assign(response.checkout_url)
      } else {
        toast.error("Could not start checkout. Please try again.")
        setIsRedirecting(false)
      }
    } catch (error) {
      console.error("[v0] Checkout redirect failed:", error)
      toast.error("Failed to start checkout")
      setIsRedirecting(false)
    }
  }

  return (
    <div className="relative z-10 px-6 py-8 lg:px-8">
      <div className="max-w-4xl mx-auto">
        <button
          type="button"
          onClick={() => router.back()}
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-6 transition-colors group"
        >
          <ArrowLeft className="h-4 w-4 transition-transform group-hover:-translate-x-1" />
          Back
        </button>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <h1 className="text-2xl font-bold text-foreground text-balance">Review your subscription</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Confirm the details below. Payment is completed securely through Stripe.
          </p>
        </motion.div>

        <div className="mt-8 grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* Plan summary */}
          <motion.div
            className="lg:col-span-3 rounded-2xl border border-border bg-card p-6"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.05 }}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 shadow-lg shadow-emerald-500/30">
                  <PlanIcon className="h-6 w-6 text-white" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-semibold text-foreground">{plan.name}</h2>
                    {plan.popular && (
                      <span className="rounded-full border border-primary/20 bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
                        Most popular
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">{plan.tagline}</p>
                </div>
              </div>
            </div>

            <div className="mt-6 border-t border-border pt-5">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-3">What&apos;s included</p>
              <ul className="space-y-2.5">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-center gap-2.5 text-sm text-foreground">
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-success/10 shrink-0">
                      <Check className="h-3 w-3 text-success" />
                    </span>
                    {feature}
                  </li>
                ))}
              </ul>
            </div>
          </motion.div>

          {/* Order summary */}
          <motion.div
            className="lg:col-span-2"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.1 }}
          >
            <div className="rounded-2xl border border-border bg-card p-6 sticky top-6">
              <h2 className="text-sm font-semibold text-foreground mb-4">Order summary</h2>

              <div className="space-y-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">{plan.name} plan</span>
                  <span className="font-medium text-foreground tabular-nums">{priceLabel}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Billing period</span>
                  <span className="text-foreground capitalize">{interval}</span>
                </div>
              </div>

              <div className="my-4 border-t border-border" />

              <div className="flex items-baseline justify-between">
                <span className="text-sm font-medium text-foreground">Due today</span>
                <span className="text-2xl font-bold text-foreground tabular-nums">
                  {priceLabel}
                  {plan.price !== null && plan.price > 0 && (
                    <span className="text-sm font-normal text-muted-foreground">/mo</span>
                  )}
                </span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Taxes are calculated at checkout. Cancel anytime from billing settings.
              </p>

              <Button className="mt-5 w-full gap-2" size="lg" onClick={handleCheckout} disabled={isRedirecting}>
                {isRedirecting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Redirecting to Stripe…
                  </>
                ) : (
                  <>
                    <Lock className="h-4 w-4" />
                    Continue to secure checkout
                  </>
                )}
              </Button>

              <div className="mt-4 flex items-center justify-center gap-2 text-xs text-muted-foreground">
                <ShieldCheck className="h-3.5 w-3.5 text-success" />
                <span>Encrypted &amp; processed by Stripe</span>
              </div>

              <p className="mt-3 text-center text-[11px] text-muted-foreground">
                You&apos;ll be redirected to Stripe to enter payment details. We never store your card.
              </p>
            </div>

            <div className="mt-3 text-center">
              <Button variant="link" size="sm" className="h-auto p-0 text-xs text-muted-foreground" asChild>
                <Link href="/settings/billing">
                  <ExternalLink className="mr-1 h-3 w-3" />
                  Compare all plans
                </Link>
              </Button>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  )
}

export default function CheckoutPage() {
  return (
    <AppShell>
      <div className="relative flex-1 overflow-auto">
        {/* Ambient brand backdrop — consistent with the billing settings page */}
        <div className="fixed inset-0 pointer-events-none z-0">
          <MorphingBackground colors={["emerald", "blue", "cyan"]} />
          <div className="absolute inset-0 bg-background/95 backdrop-blur-3xl" />
          <div className="absolute top-0 right-0">
            <GlowOrb size={360} color="emerald" intensity={0.25} />
          </div>
        </div>

        <Suspense
          fallback={
            <div className="relative z-10 flex items-center justify-center py-32">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          }
        >
          <CheckoutContent />
        </Suspense>
      </div>
    </AppShell>
  )
}
