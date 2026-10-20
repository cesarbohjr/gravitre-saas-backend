"use client"

/**
 * Billing and plan (design p16): plan card with auto renew, current usage,
 * Stripe invoices and the payment method on file. Every figure comes from
 * /api/billing (Stripe-reconciled) or the plan catalog; checkout, top-ups,
 * plan change and cancel run through the existing backend flows.
 */
import { useState, useEffect, useMemo, Suspense } from "react"
import useSWR from "swr"
import Link from "next/link"
import { AlertCircle, Check, CheckCircle2, Loader2, ShieldCheck } from "lucide-react"
import { useRouter, useSearchParams } from "next/navigation"
import { AppShell } from "@/components/gravitre/app-shell"
import { SettingsShell } from "@/components/settings/settings-shell"
import {
  BillingInvoicesCard,
  BillingPaymentCard,
  BillingPlanCard,
  BillingUsageCard,
} from "@/components/settings/billing-cards"
import { SetNote, SetSwitch } from "@/components/settings/settings-kit"
import { MspBilledGate } from "@/components/settings/msp-billed-gate"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { useSettingsSectionNav } from "@/lib/settings-nav"
import { billingApi, ApiRequestError } from "@/lib/api"
import { apiFetch, fetcher as apiFetcher } from "@/lib/fetcher"
import { ensureSelectedOrg } from "@/lib/org-context"
import { SELECTABLE_PLANS, getPlan, formatPlanPrice, planDirection, type PlanCode } from "@/lib/plans"
import {
  autoRenewLine,
  billingStatusMeta,
  defaultPaymentMethod,
  invoiceRows,
  longDate,
  planPriceLabel,
  renewalLine,
  shortDate,
  subscriptionStatus,
  usageTiles,
  type InvoiceRow,
} from "@/lib/settings-api/billing"
import { toast } from "sonner"
import { PromotionNotices } from "@/components/billing/promotion-notices"
import { UpgradePromoField } from "@/components/billing/upgrade-promo-field"
import type { AppliedPromo } from "@/components/billing/promo-code-field"
import { withPromoParam } from "@/lib/promotions"

export default function BillingPage() {
  const { isAdmin, showAdmin, pending: adminPending } = useOrgAdmin()
  const onSectionChange = useSettingsSectionNav("billing")
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  return (
    <AppShell title="Settings">
      <div data-composition="configure" className="h-full min-h-0">
        <Suspense
          fallback={
            <div className="flex h-full items-center justify-center">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            </div>
          }
        >
          <SettingsShell
            activeSection="billing"
            isAdmin={showAdmin}
            mobileMenuOpen={mobileMenuOpen}
            onMobileMenuOpenChange={setMobileMenuOpen}
            onSectionChange={onSectionChange}
            hideHeader
          >
            {/* Plan and usage render straight away; admin-only billing controls
                stay disabled until the server confirms the role. */}
            <MspBilledGate>
              <BillingPageInner isAdmin={isAdmin} adminChecking={!isAdmin && (adminPending || showAdmin)} />
            </MspBilledGate>
          </SettingsShell>
        </Suspense>
      </div>
    </AppShell>
  )
}

function BillingPageInner({ isAdmin, adminChecking = false }: { isAdmin: boolean; adminChecking?: boolean }) {
  const { user } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()

  // Modal states
  const [upgradeModalOpen, setUpgradeModalOpen] = useState(false)
  const [cancelModalOpen, setCancelModalOpen] = useState(false)
  const [updateCardModalOpen, setUpdateCardModalOpen] = useState(false)
  const [editAddressModalOpen, setEditAddressModalOpen] = useState(false)
  const [topUpModalOpen, setTopUpModalOpen] = useState(false)
  const [selectedTopUpMinutes, setSelectedTopUpMinutes] = useState<60 | 300 | 1200>(60)
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null)
  const [appliedPromo, setAppliedPromo] = useState<AppliedPromo | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [autoTopupSaving, setAutoTopupSaving] = useState(false)
  // Set when Stripe returns with ?topup=success. The query param is stripped
  // immediately by router.replace, so the confirmation has to be held in state
  // or it would flash for one frame and vanish.
  const [topUpCredited, setTopUpCredited] = useState(false)

  // Live subscription — never invent Node while loading or on error (that regression
  // made Command orgs look like $49 Node when /api/billing failed or was slow).
  const { data: overview, error: overviewError, isLoading: overviewLoading, mutate: mutateOverview } = useSWR(
    user ? "billing-overview" : null,
    () => billingApi.overview(),
    { revalidateOnFocus: true, revalidateOnReconnect: true, refreshInterval: 120_000 },
  )
  const { data: voiceAccess, mutate: mutateVoiceAccess } = useSWR(
    user ? "/api/settings/voice-access" : null,
    apiFetcher,
    { revalidateOnFocus: true, revalidateOnReconnect: true },
  )
  const voiceSettings = (voiceAccess as {
    voice?: {
      voice_enabled?: boolean
      voice_minutes_prepaid?: number
      voice_auto_topup_enabled?: boolean
      voice_auto_topup_minutes?: number
      voice_auto_topup_threshold_minutes?: number
      voice_auto_topup_max_charge_cents?: number
    }
  } | undefined)?.voice
  const voiceOrgEnabled = voiceSettings?.voice_enabled !== false
  const subscription = overview?.subscription
  const resolvedTierRaw = (overview?.usage?.tier || subscription?.tier || "").toString().trim().toLowerCase()
  const currentTier = (resolvedTierRaw || null) as PlanCode | null
  const currentPlan = currentTier ? getPlan(currentTier) : null
  const planKnown = Boolean(currentPlan)
  // Never invent Active when status is missing — that left cancelled orgs looking live
  // after subscription.deleted wrote only a partial cancel. Prefer overview.billing_status.
  const subStatus = subscriptionStatus(overview)
  const usageFromApi = overview?.usage
  const showVoiceBilling = Boolean(usageFromApi?.voice_minutes_billing_visible)
  const voiceRateUsd = Number(usageFromApi?.voice_minute_overage_rate_usd ?? 0.12)
  const topUpCostUsd = selectedTopUpMinutes * voiceRateUsd

  const tiles = useMemo(() => usageTiles(usageFromApi, currentTier), [usageFromApi, currentTier])
  const invoices = useMemo(() => invoiceRows(overview?.invoices), [overview?.invoices])
  const cardOnFile = defaultPaymentMethod(overview?.payment_methods)
  const status = billingStatusMeta(subStatus, overviewLoading)
  const renewalLabel = renewalLine(subStatus, subscription?.current_period_end, Boolean(subscription?.cancel_at_period_end))

  const autoRenewEnabled =
    planKnown &&
    subStatus !== "canceled" &&
    subStatus !== "unknown" &&
    !subscription?.cancel_at_period_end
  // Stripe's unit amount for the live Price on the subscription (grandfathered
  // prices stay put); the catalog list price only when Stripe gave no Price.
  const price =
    planKnown && currentPlan
      ? planPriceLabel({
          unitAmountCents: subscription?.plan_unit_amount_cents ?? null,
          interval: subscription?.plan_billing_interval ?? null,
          catalogPrice: formatPlanPrice(currentPlan),
          catalogMonthly: currentPlan.price !== null && currentPlan.price > 0,
        })
      : null

  const planTitle = planKnown
    ? `${currentPlan!.name} plan`
    : overviewLoading
      ? "Loading plan…"
      : overviewError
        ? "Plan unavailable"
        : "Plan unknown"
  const planSubline = planKnown
    ? (renewalLabel ?? currentPlan!.tagline)
    : overviewError
      ? "Could not load billing status. Retry or contact support."
      : "Confirming your subscription with Stripe…"

  useEffect(() => {
    if (searchParams.get("status") === "success") {
      toast.success("Subscription activated. Full access is being restored.")
      router.replace("/settings/billing")
    }
    const topup = searchParams.get("topup")
    if (topup === "success") {
      toast.success("Voice Minutes top-up completed. Minutes are available now.")
      setTopUpCredited(true)
      void mutateOverview()
      void mutateVoiceAccess()
      router.replace("/settings/billing")
    } else if (topup === "cancelled") {
      toast.message("Top-up cancelled. No charge was made.")
      router.replace("/settings/billing")
    }
  }, [router, searchParams, mutateOverview, mutateVoiceAccess])

  const handleVoiceTopUp = async () => {
    if (!user) {
      toast.error("Sign in required")
      return
    }
    setIsProcessing(true)
    try {
      const result = await billingApi.createVoiceMinutesTopUp(selectedTopUpMinutes)
      if (!result.checkout_url) throw new Error("Missing checkout URL")
      window.location.href = result.checkout_url
    } catch (error) {
      console.error("[billing] voice top-up failed:", error)
      const msg =
        error instanceof ApiRequestError
          ? error.message
          : "Could not start Voice Minutes top-up. Confirm a payment method on your plan first."
      toast.error(msg)
      setIsProcessing(false)
    }
  }

  const handleAutoTopupToggle = async (enabled: boolean) => {
    setAutoTopupSaving(true)
    try {
      const res = await apiFetch("/api/settings/voice-access", {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          auto_topup_enabled: enabled,
          auto_topup_minutes: voiceSettings?.voice_auto_topup_minutes ?? 60,
          auto_topup_threshold_minutes: voiceSettings?.voice_auto_topup_threshold_minutes ?? 15,
        }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body?.detail || "Failed to update auto top-up")
      }
      toast.success(enabled ? "Auto top-up enabled" : "Auto top-up disabled")
      await mutateVoiceAccess()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to update auto top-up")
    } finally {
      setAutoTopupSaving(false)
    }
  }

  // Handler functions
  const handleUpgrade = async (planCode: string) => {
    if (!user) {
      toast.error("Sign in required")
      return
    }
    const orgId = await ensureSelectedOrg(true)
    if (!orgId) {
      toast.error("Could not resolve your organization. Refresh the page and try again.")
      return
    }
    setSelectedPlan(planCode)
    setUpgradeModalOpen(false)
    router.push(withPromoParam(`/settings/billing/checkout?plan=${planCode}&interval=monthly`, appliedPromo?.code))
  }

  const handleCancelSubscription = async () => {
    if (!user) {
      toast.error("Sign in required")
      return
    }
    setIsProcessing(true)
    try {
      await billingApi.cancelSubscription(true)
      toast.success("Subscription will cancel at period end")
      await mutateOverview()
    } catch (error) {
      console.error("[billing] Cancel subscription failed:", error)
      toast.error("Failed to cancel subscription")
    } finally {
      setIsProcessing(false)
      setCancelModalOpen(false)
    }
  }

  // Auto renew is Stripe's cancel_at_period_end: off schedules the cancel at
  // period end, on reactivates the same subscription.
  const handleAutoRenewToggle = async (enabled: boolean) => {
    if (!user) {
      toast.error("Sign in required")
      return
    }
    if (!isAdmin) {
      toast.error("Only organization admins can change auto renew")
      return
    }
    setIsProcessing(true)
    try {
      if (enabled) {
        await billingApi.reactivateSubscription()
        toast.success("Auto renew is on. Your plan renews automatically.")
      } else {
        await billingApi.cancelSubscription(true)
        toast.success("Auto renew is off. You keep access until the end of this billing period.")
      }
      await mutateOverview()
    } catch (error) {
      console.error("[billing] auto-renew toggle failed:", error)
      toast.error(enabled ? "Failed to turn on auto renew" : "Failed to turn off auto renew")
    } finally {
      setIsProcessing(false)
    }
  }

  const handleUpdateCard = async () => {
    if (!user) {
      toast.error("Sign in required")
      return
    }
    setIsProcessing(true)
    try {
      const response = await billingApi.createPortalSession()
      if (response.portal_url) {
        window.location.assign(response.portal_url)
      }
    } catch (error) {
      console.error("[billing] Portal session failed:", error)
      toast.error("Failed to open billing portal")
    } finally {
      setIsProcessing(false)
      setUpdateCardModalOpen(false)
    }
  }

  const handleUpdateAddress = async () => {
    if (!user) {
      toast.error("Sign in required")
      return
    }
    setIsProcessing(true)
    try {
      // Billing address is Stripe-owned; the backend exposes the secure customer
      // portal, not an address-update API. Never pretend a local edit persisted.
      const response = await billingApi.createPortalSession()
      if (!response.portal_url) throw new Error("Billing portal unavailable")
      window.location.assign(response.portal_url)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not open billing portal")
    } finally {
      setIsProcessing(false)
    }
  }

  /** "Download all": a CSV of every invoice Stripe returns for this org. */
  const handleExportAll = () => {
    void (async () => {
      if (!user) {
        toast.error("Sign in required")
        return
      }
      try {
        const response = await billingApi.listInvoices()
        const csvContent =
          "Invoice ID,Number,Amount (cents),Currency,Status,Period Start,Period End,Created At,PDF\n" +
          (response.invoices || [])
            .map((inv) => {
              const extra = inv as typeof inv & { number?: string | null }
              return [
                inv.id,
                extra.number ?? "",
                inv.amount_cents,
                inv.currency,
                inv.status,
                inv.period_start,
                inv.period_end,
                inv.created_at,
                inv.pdf_url ?? "",
              ]
                .map((cell) => `"${String(cell ?? "").replace(/"/g, '""')}"`)
                .join(",")
            })
            .join("\n")
        const blob = new Blob([csvContent], { type: "text/csv" })
        const url = URL.createObjectURL(blob)
        const a = document.createElement("a")
        a.href = url
        a.download = "invoices.csv"
        a.click()
        URL.revokeObjectURL(url)
      } catch (error) {
        console.error("[billing] Export invoices failed:", error)
        toast.error("Failed to export invoices")
      }
    })()
  }

  const handleDownloadInvoice = (invoice: InvoiceRow) => {
    if (invoice.downloadUrl) {
      window.open(invoice.downloadUrl, "_blank", "noopener,noreferrer")
      return
    }
    void (async () => {
      if (!user) {
        toast.error("Sign in required")
        return
      }
      try {
        const response = await billingApi.downloadInvoice(invoice.id)
        if (!response.ok) {
          throw new Error(`Invoice download failed (${response.status})`)
        }
        const pdfUrl = await response.text()
        if (pdfUrl) {
          window.open(pdfUrl, "_blank", "noopener,noreferrer")
        }
      } catch (error) {
        console.error("[billing] Download invoice failed:", error)
        toast.error("Failed to download invoice")
      }
    })()
  }

  const loadingOverview = overviewLoading && !overview
  const overviewFailed = Boolean(overviewError) && !overview

  return (
    <>
      <h1 className="sr-only">Billing and plan</h1>
      <BillingPlanCard
        loading={loadingOverview}
        error={overviewFailed}
        onRetry={() => void mutateOverview()}
        title={planTitle}
        status={status}
        subline={planSubline}
        price={price}
        showAutoRenew={planKnown && subStatus !== "canceled"}
        autoRenewOn={autoRenewEnabled}
        autoRenewText={autoRenewLine(autoRenewEnabled, subscription?.current_period_end)}
        autoRenewDisabled={isProcessing || overviewLoading || !isAdmin}
        autoRenewHint={!isAdmin && !adminChecking ? "Admin access is required to change auto renew." : null}
        onAutoRenew={(checked) => void handleAutoRenewToggle(checked)}
        canUpgrade={planKnown}
        onUpgrade={() => setUpgradeModalOpen(true)}
        canCancel={planKnown && autoRenewEnabled && isAdmin}
        onCancel={() => setCancelModalOpen(true)}
      />

      <PromotionNotices enabled={Boolean(user)} />

      <BillingUsageCard
        loading={loadingOverview}
        error={overviewFailed}
        onRetry={() => void mutateOverview()}
        periodEnd={shortDate(subscription?.current_period_end)}
        tiles={tiles}
      >
        {showVoiceBilling ? (
          <div className="gs-row-sec" style={{ alignItems: "flex-start" }}>
            <div className="gs-what">
              <b>Voice Minutes top-up</b>
              <span>Your plan allotment is used first. Prepaid packs are spent next, before any overage is billed.</span>
              <dl className="bl-voice-figs" style={{ marginTop: 12 }}>
                <div>
                  <dt>Prepaid balance</dt>
                  <dd>{(voiceSettings?.voice_minutes_prepaid ?? 0).toLocaleString()} min</dd>
                </div>
                <div>
                  <dt>Rate</dt>
                  <dd>${voiceRateUsd.toFixed(2)}/min</dd>
                </div>
              </dl>
            </div>
            <button
              type="button"
              className="gs-btn dark sm"
              onClick={() => setTopUpModalOpen(true)}
              disabled={!voiceOrgEnabled || isProcessing}
            >
              Add minutes
            </button>
            <div className="gs-under" style={{ marginLeft: 0, display: "grid", gap: 10 }}>
              {topUpCredited ? (
                <SetNote tone="green" icon={CheckCircle2}>
                  Payment succeeded. Your prepaid balance is now{" "}
                  <strong>{(voiceSettings?.voice_minutes_prepaid ?? 0).toLocaleString()} min</strong>.
                </SetNote>
              ) : null}
              {!voiceOrgEnabled ? (
                <SetNote tone="amber" icon={AlertCircle}>
                  Voice is turned off for this organization. Turn it on under Meson add-ons before topping up.
                </SetNote>
              ) : null}
              <div className="bl-renew">
                <div>
                  <b>Auto top-up</b>
                  <span>
                    {voiceSettings?.voice_auto_topup_enabled ? (
                      <>
                        When Voice Minutes drop below{" "}
                        <strong>{voiceSettings?.voice_auto_topup_threshold_minutes ?? 15} min</strong>, we automatically
                        charge{" "}
                        <strong>
                          ${((voiceSettings?.voice_auto_topup_minutes ?? 60) * voiceRateUsd).toFixed(2)}
                        </strong>{" "}
                        for <strong>{voiceSettings?.voice_auto_topup_minutes ?? 60} min</strong>.
                      </>
                    ) : (
                      "Not configured. Voice sessions stop when your balance runs out."
                    )}
                  </span>
                  {voiceSettings?.voice_auto_topup_enabled ? (
                    <span style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 4 }}>
                      <ShieldCheck size={14} aria-hidden />
                      Hard cap: never more than $
                      {((voiceSettings?.voice_auto_topup_max_charge_cents ?? 3600) / 100).toFixed(2)} per automatic
                      charge.
                    </span>
                  ) : null}
                </div>
                <SetSwitch
                  checked={Boolean(voiceSettings?.voice_auto_topup_enabled)}
                  disabled={!voiceOrgEnabled || autoTopupSaving}
                  onChange={(checked) => void handleAutoTopupToggle(checked)}
                  label="Enable voice minutes auto top-up"
                />
              </div>
            </div>
          </div>
        ) : null}
      </BillingUsageCard>

      <div className="bl-row">
        <BillingInvoicesCard
          loading={loadingOverview}
          error={overviewFailed}
          onRetry={() => void mutateOverview()}
          rows={invoices}
          onDownload={handleDownloadInvoice}
          onDownloadAll={handleExportAll}
        />
        <BillingPaymentCard
          loading={loadingOverview}
          error={overviewFailed}
          card={cardOnFile}
          canManage={isAdmin}
          busy={isProcessing}
          onUpdate={() => setUpdateCardModalOpen(true)}
          onEditAddress={() => setEditAddressModalOpen(true)}
        />
      </div>

      <SetNote>
        Need help with billing? Email <a href="mailto:billing@gravitre.app">billing@gravitre.app</a> or read the{" "}
        <Link href="/docs">billing FAQ</Link>.
      </SetNote>

      <Dialog open={topUpModalOpen} onOpenChange={setTopUpModalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Add voice minutes</DialogTitle>
            <DialogDescription>
              Pick a pack. You&apos;ll confirm the payment on Stripe, and minutes credit as soon as it succeeds.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 py-2" role="radiogroup" aria-label="Voice minute packs">
            {([60, 300, 1200] as const).map((minutes) => {
              const cost = minutes * voiceRateUsd
              const selected = selectedTopUpMinutes === minutes
              return (
                <button
                  key={minutes}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  onClick={() => setSelectedTopUpMinutes(minutes)}
                  disabled={isProcessing}
                  className={cn(
                    "flex w-full items-center justify-between gap-4 rounded-xl border px-4 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    selected ? "border-primary bg-primary/5" : "border-divide bg-[color:var(--g-surface-1)] hover:border-divide",
                    isProcessing && "opacity-60",
                  )}
                >
                  <span className="min-w-0">
                    <span className="block text-sm font-medium tabular-nums text-foreground">
                      {minutes.toLocaleString()} minutes
                    </span>
                    <span className="mt-0.5 block text-[11px] tabular-nums text-muted-foreground">
                      ${voiceRateUsd.toFixed(2)} per minute
                    </span>
                  </span>
                  {/* The real dollar amount sits on the pack itself, so the price
                      is visible before any confirmation step. */}
                  <span className="shrink-0 text-base font-semibold tabular-nums text-foreground">${cost.toFixed(2)}</span>
                </button>
              )
            })}
          </div>
          <DialogFooter className="flex-col gap-3 sm:flex-col sm:items-stretch">
            {/* Redirecting to Stripe unmounts this dialog, so an ambiguous
                spinner is the exact state that stranded users before. Name the
                step instead, and say plainly that a stale tab is safe to retry. */}
            {isProcessing ? (
              <p className="flex items-start gap-2 rounded-xl border border-info/30 bg-info/[0.06] px-3 py-2 text-xs text-foreground">
                <Loader2 className="mt-0.5 h-3.5 w-3.5 shrink-0 animate-spin text-info" aria-hidden />
                <span>
                  Creating a secure Stripe checkout, then redirecting you. If this tab is still here in a few seconds,
                  close the dialog and try again. No charge is made until you confirm on Stripe.
                </span>
              </p>
            ) : (
              <p className="text-[11px] leading-relaxed text-muted-foreground">
                Total charged today:{" "}
                <strong className="font-semibold tabular-nums text-foreground">${topUpCostUsd.toFixed(2)}</strong> for{" "}
                {selectedTopUpMinutes.toLocaleString()} minutes. Single charges are capped at $120.
              </p>
            )}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setTopUpModalOpen(false)} disabled={isProcessing}>
                Cancel
              </Button>
              <Button onClick={() => void handleVoiceTopUp()} disabled={isProcessing || !voiceOrgEnabled}>
                {isProcessing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                {isProcessing ? "Opening Stripe…" : `Continue · $${topUpCostUsd.toFixed(2)}`}
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Upgrade Plan Modal */}
      <Dialog open={upgradeModalOpen} onOpenChange={setUpgradeModalOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Upgrade your plan</DialogTitle>
            <DialogDescription>
              Choose a plan that best fits your needs. You can upgrade or downgrade at any time.
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-1 gap-4 py-4 md:grid-cols-3" role="radiogroup" aria-label="Plans">
            {SELECTABLE_PLANS.map((plan) => {
              const PlanIcon = plan.icon
              const isCurrent = planKnown && plan.code === currentTier
              const isSelected = selectedPlan === plan.code
              const direction = planDirection(plan.code, currentTier ?? "free")

              return (
                <button
                  type="button"
                  key={plan.code}
                  role="radio"
                  aria-checked={isSelected}
                  disabled={isCurrent}
                  className={cn(
                    "relative rounded-xl border p-4 text-left transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    isCurrent
                      ? "cursor-default border-success/50 bg-success/5"
                      : isSelected
                        ? "border-primary bg-primary/5 ring-2 ring-primary/30"
                        : "border-border hover:-translate-y-0.5 hover:border-foreground/20",
                  )}
                  onClick={() => !isCurrent && setSelectedPlan(plan.code)}
                >
                  {(isCurrent || plan.popular) && (
                    <span
                      className={cn(
                        "absolute -top-2 right-2 rounded-full border px-2 py-0.5 text-[10px] font-medium",
                        isCurrent ? "border-success/20 bg-success/10 text-success" : "border-primary/20 bg-primary/10 text-primary",
                      )}
                    >
                      {isCurrent ? "Current" : "Most popular"}
                    </span>
                  )}
                  <div className="mb-3 flex items-center gap-2">
                    <div className={cn("flex h-8 w-8 items-center justify-center rounded-lg", isCurrent ? "bg-success/10" : "bg-secondary")}>
                      <PlanIcon className={cn("h-4 w-4", isCurrent ? "text-success" : "text-muted-foreground")} />
                    </div>
                    <span className="font-medium">{plan.name}</span>
                  </div>
                  <p className="mb-3 text-2xl font-bold">
                    {formatPlanPrice(plan)}
                    <span className="text-sm font-normal text-muted-foreground">/mo</span>
                  </p>
                  <ul className="space-y-1.5">
                    {plan.features.map((feature, i) => (
                      <li key={i} className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Check className="h-3 w-3 text-success" />
                        {feature}
                      </li>
                    ))}
                  </ul>
                  {!isCurrent && (
                    <p className="mt-3 text-xs font-medium text-muted-foreground">
                      {direction === "downgrade" ? "Downgrade" : "Upgrade"}
                    </p>
                  )}
                </button>
              )
            })}
          </div>
          {upgradeModalOpen ? <UpgradePromoField plan={selectedPlan} onApplied={setAppliedPromo} /> : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setUpgradeModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => selectedPlan && handleUpgrade(selectedPlan)} disabled={!selectedPlan}>
              Upgrade plan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Cancel Subscription Modal */}
      <AlertDialog open={cancelModalOpen} onOpenChange={setCancelModalOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel subscription</AlertDialogTitle>
            <AlertDialogDescription>
              Your subscription stops renewing. You keep every feature until the end of this billing period
              {longDate(subscription?.current_period_end) ? ` (${longDate(subscription?.current_period_end)})` : ""}, then
              lose access to paid features. You can turn auto renew back on before then.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep subscription</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={handleCancelSubscription}
              disabled={isProcessing}
            >
              {isProcessing ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Cancelling…
                </>
              ) : (
                "Yes, cancel"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Stripe handles card entry; never collect card numbers or CVC in a local-only form. */}
      <Dialog open={updateCardModalOpen} onOpenChange={setUpdateCardModalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Update payment method</DialogTitle>
            <DialogDescription>
              Open the secure billing portal to view or change your payment method. Card details are never entered
              into Gravitre.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setUpdateCardModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => void handleUpdateCard()} disabled={isProcessing}>
              {isProcessing ? "Opening…" : "Open secure billing portal"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Stripe is the source of truth for invoice billing details. */}
      <Dialog open={editAddressModalOpen} onOpenChange={setEditAddressModalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Update billing address</DialogTitle>
            <DialogDescription>
              Your billing address is managed securely in the billing portal. Gravitre does not save address changes
              locally.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditAddressModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => void handleUpdateAddress()} disabled={isProcessing}>
              {isProcessing ? "Opening…" : "Open secure billing portal"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
