"use client"

import { useState, useMemo } from "react"
import { useRouter } from "next/navigation"
import useSWR from "swr"
import { motion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  MorphingBackground,
  GlowOrb,
  StatusBeacon,
} from "@/components/gravitre/premium-effects"
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
import {
  ArrowLeft,
  CreditCard,
  Download,
  Check,
  Zap,
  FileText,
  Cpu,
  Activity,
  Clock,
  ExternalLink,
  Sparkles,
  Crown,
  TrendingUp,
  Shield,
  ChevronRight,
  Loader2,
  Mail,
  Receipt,
} from "lucide-react"
import Link from "next/link"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth-context"
import { billingApi } from "@/lib/api"
import {
  SELECTABLE_PLANS,
  getPlan,
  formatPlanPrice,
  planDirection,
  type PlanCode,
} from "@/lib/plans"
import type { Invoice, PaymentMethod, BillingUsageResponse } from "@/types/api"
import { toast } from "sonner"

// ---- formatting helpers (pure, no fabricated data) ----
function formatMoney(cents: number, currency = "usd"): string {
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: currency.toUpperCase(),
    }).format(cents / 100)
  } catch {
    return `$${(cents / 100).toFixed(2)}`
  }
}

function formatDate(value: string | undefined): string {
  if (!value) return "—"
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return "—"
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
}

function compactNumber(n: number): string {
  return new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(n)
}

type UsageCard = {
  key: string
  name: string
  icon: typeof Zap
  used: number
  limit: number | null
}

function buildUsageCards(usage: BillingUsageResponse | undefined): UsageCard[] {
  if (!usage) return []
  const t = usage.totals
  return [
    { key: "outputs", name: "Outputs", icon: FileText, used: t.outputs, limit: usage.included_outputs ?? null },
    { key: "workflow_runs", name: "Workflow runs", icon: Zap, used: t.workflow_runs, limit: null },
    { key: "api_calls", name: "API calls", icon: Activity, used: t.api_calls, limit: null },
    { key: "ai_tokens", name: "AI tokens", icon: Cpu, used: t.ai_tokens, limit: null },
  ]
}

function invoiceStatusTone(status: string): { label: string; classes: string } {
  const s = status.toLowerCase()
  if (s === "paid") return { label: "Paid", classes: "bg-success/10 text-success" }
  if (s === "open" || s === "pending") return { label: "Open", classes: "bg-warning/10 text-warning" }
  if (s === "void" || s === "uncollectible" || s === "failed")
    return { label: status, classes: "bg-destructive/10 text-destructive" }
  return { label: status, classes: "bg-muted text-muted-foreground" }
}

export default function BillingPage() {
  const { user } = useAuth()
  const router = useRouter()

  const [upgradeModalOpen, setUpgradeModalOpen] = useState(false)
  const [cancelModalOpen, setCancelModalOpen] = useState(false)
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)

  // Single source of live billing truth: subscription, usage, invoices, and
  // payment methods all come from the backend. Nothing on this page is mocked.
  const { data: overview, isLoading } = useSWR(
    user ? "billing-overview" : null,
    () => billingApi.overview(),
    { revalidateOnFocus: false },
  )

  const subscription = overview?.subscription
  const currentTier = (subscription?.tier ?? "node") as PlanCode
  const currentPlan = getPlan(currentTier)
  const subStatus = subscription?.status ?? "active"

  const usageCards = useMemo(() => buildUsageCards(overview?.usage), [overview?.usage])
  const invoices: Invoice[] = useMemo(() => overview?.invoices ?? [], [overview?.invoices])
  const paymentMethod: PaymentMethod | undefined = useMemo(() => {
    const methods = overview?.payment_methods ?? []
    return methods.find((m) => m.is_default) ?? methods[0]
  }, [overview?.payment_methods])

  const overageOutputs = overview?.usage?.overage_outputs ?? 0
  const overageCost = overview?.usage?.overage_cost_usd ?? 0
  const includedOutputs = overview?.usage?.included_outputs ?? null

  const statusDisplay: Record<
    string,
    { label: string; classes: string; beacon: "active" | "warning" | "error" | "idle" }
  > = {
    active: { label: "Active", classes: "bg-success/10 text-success border-success/20", beacon: "active" },
    trialing: { label: "Trial", classes: "bg-info/10 text-info border-info/20", beacon: "active" },
    past_due: { label: "Past due", classes: "bg-warning/10 text-warning border-warning/20", beacon: "warning" },
    canceled: { label: "Canceled", classes: "bg-muted text-muted-foreground border-border", beacon: "idle" },
  }
  const status = statusDisplay[subStatus] ?? statusDisplay.active

  const periodEndLabel = (() => {
    if (!subscription?.current_period_end) return null
    const d = new Date(subscription.current_period_end)
    return Number.isNaN(d.getTime())
      ? null
      : d.toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" })
  })()

  const renewalLabel = (() => {
    if (!periodEndLabel) return null
    if (subStatus === "canceled" || subscription?.cancel_at_period_end) return `Access ends ${periodEndLabel}`
    if (subStatus === "trialing") return `Trial ends ${periodEndLabel}`
    return `Renews ${periodEndLabel}`
  })()

  const periodRangeLabel = (() => {
    if (!subscription?.current_period_start || !subscription?.current_period_end) return null
    return `${formatDate(subscription.current_period_start)} – ${formatDate(subscription.current_period_end)}`
  })()

  // ---- handlers (all real API calls) ----
  // Route to the branded checkout review step, which performs the real Stripe
  // redirect. This gives users an order-summary confirmation before payment.
  const handleUpgrade = (planCode: string) => {
    if (!user) {
      toast.error("Sign in required")
      return
    }
    setUpgradeModalOpen(false)
    router.push(`/settings/billing/checkout?plan=${encodeURIComponent(planCode)}`)
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
    } catch (error) {
      console.error("[v0] Cancel subscription failed:", error)
      toast.error("Failed to cancel subscription")
    } finally {
      setIsProcessing(false)
      setCancelModalOpen(false)
    }
  }

  // Card and billing-address management are owned by Stripe's secure portal —
  // we never collect raw card numbers in our own UI.
  const openBillingPortal = async () => {
    if (!user) {
      toast.error("Sign in required")
      return
    }
    setIsProcessing(true)
    try {
      const response = await billingApi.createPortalSession()
      if (response.portal_url) {
        window.location.assign(response.portal_url)
      } else {
        toast.error("Could not open the billing portal. Please try again.")
      }
    } catch (error) {
      console.error("[v0] Portal session failed:", error)
      toast.error("Failed to open billing portal")
    } finally {
      setIsProcessing(false)
    }
  }

  const handleExportAll = () => {
    void (async () => {
      if (!user) {
        toast.error("Sign in required")
        return
      }
      try {
        const response = await billingApi.listInvoices()
        const rows = response.invoices || []
        if (rows.length === 0) {
          toast.info("No invoices to export yet")
          return
        }
        const csvContent =
          "Invoice ID,Amount (cents),Currency,Status,Period Start,Period End,Created At\n" +
          rows
            .map(
              (inv) =>
                `${inv.id},${inv.amount_cents},${inv.currency},${inv.status},${inv.period_start},${inv.period_end},${inv.created_at}`,
            )
            .join("\n")
        const blob = new Blob([csvContent], { type: "text/csv" })
        const url = URL.createObjectURL(blob)
        const a = document.createElement("a")
        a.href = url
        a.download = "invoices.csv"
        a.click()
        URL.revokeObjectURL(url)
      } catch (error) {
        console.error("[v0] Export invoices failed:", error)
        toast.error("Failed to export invoices")
      }
    })()
  }

  const handleDownloadInvoice = (invoiceId: string) => {
    void (async () => {
      if (!user) {
        toast.error("Sign in required")
        return
      }
      try {
        const response = await billingApi.downloadInvoice(invoiceId)
        if (!response.ok) {
          throw new Error(`Invoice download failed (${response.status})`)
        }
        const pdfUrl = await response.text()
        if (pdfUrl) {
          window.open(pdfUrl, "_blank", "noopener,noreferrer")
        }
      } catch (error) {
        console.error("[v0] Download invoice failed:", error)
        toast.error("Failed to download invoice")
      }
    })()
  }

  const hasUsage = usageCards.length > 0

  return (
    <AppShell>
      <div className="relative flex-1 overflow-auto">
        {/* Ambient brand backdrop — emerald is Gravitre's premium signature.
            (Brand primary purple is reserved for primary actions, not ambience.) */}
        <div className="fixed inset-0 pointer-events-none z-0">
          <MorphingBackground colors={["emerald", "blue", "cyan"]} />
          <div className="absolute inset-0 bg-background/95 backdrop-blur-3xl" />
        </div>

        {/* Hero header */}
        <div className="relative z-10 overflow-hidden border-b border-border/50">
          <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/10 via-transparent to-teal-500/10" />
          <div className="absolute top-0 right-0 pointer-events-none">
            <GlowOrb size={400} color="emerald" intensity={0.3} />
          </div>
          <div className="absolute bottom-0 left-0 pointer-events-none">
            <GlowOrb size={300} color="cyan" intensity={0.2} />
          </div>

          <div className="relative px-6 py-8 lg:px-8">
            <div className="max-w-5xl mx-auto">
              <Link
                href="/settings"
                className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-6 transition-colors group"
              >
                <ArrowLeft className="h-4 w-4 transition-transform group-hover:-translate-x-1" />
                Back to Settings
              </Link>

              <motion.div
                className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
              >
                <div className="flex items-center gap-4">
                  <motion.div
                    className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 shadow-xl shadow-emerald-500/30 relative shrink-0"
                    animate={{ scale: [1, 1.04, 1] }}
                    transition={{ duration: 3, repeat: Infinity }}
                  >
                    <Crown className="h-7 w-7 text-white" />
                  </motion.div>
                  <div>
                    <div className="flex items-center gap-3 flex-wrap">
                      <h1 className="text-2xl font-bold text-foreground">{currentPlan.name} Plan</h1>
                      <span
                        className={cn(
                          "flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-full border",
                          status.classes,
                        )}
                      >
                        <StatusBeacon
                          status={status.beacon}
                          size="sm"
                          pulse={subStatus === "active" || subStatus === "trialing"}
                        />
                        {status.label}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground mt-0.5">{renewalLabel ?? currentPlan.tagline}</p>
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <p className="text-4xl font-bold text-foreground tracking-tight">{formatPlanPrice(currentPlan)}</p>
                    {currentPlan.price !== null && currentPlan.price > 0 && (
                      <p className="text-sm text-muted-foreground">/month</p>
                    )}
                  </div>
                  <div className="h-12 w-px bg-border" />
                  <div className="flex flex-col gap-2">
                    <Button variant="default" size="sm" className="gap-2 group" onClick={() => setUpgradeModalOpen(true)}>
                      <TrendingUp className="h-3.5 w-3.5 transition-transform group-hover:-translate-y-0.5" />
                      Change Plan
                    </Button>
                    {subStatus !== "canceled" && !subscription?.cancel_at_period_end && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-xs text-muted-foreground"
                        onClick={() => setCancelModalOpen(true)}
                      >
                        Cancel Subscription
                      </Button>
                    )}
                  </div>
                </div>
              </motion.div>
            </div>
          </div>
        </div>

        {/* Main content */}
        <div className="px-6 py-8 lg:px-8">
          <div className="max-w-5xl mx-auto space-y-10">
            {/* Usage */}
            <section>
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-muted-foreground" />
                  <h2 className="text-sm font-semibold text-foreground">Current Usage</h2>
                </div>
                {periodRangeLabel && (
                  <span className="text-xs text-muted-foreground">Billing period: {periodRangeLabel}</span>
                )}
              </div>

              {isLoading ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  {[0, 1, 2, 3].map((i) => (
                    <div key={i} className="h-36 rounded-2xl border border-border bg-card/50 animate-pulse" />
                  ))}
                </div>
              ) : hasUsage ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  {usageCards.map((metric) => {
                    const pct = metric.limit ? Math.min(100, Math.round((metric.used / metric.limit) * 100)) : null
                    const tone =
                      pct === null ? "muted" : pct >= 90 ? "destructive" : pct >= 70 ? "warning" : "success"
                    const barClass =
                      tone === "destructive" ? "bg-destructive" : tone === "warning" ? "bg-warning" : "bg-success"
                    const iconWrap =
                      tone === "destructive"
                        ? "bg-destructive/10 text-destructive"
                        : tone === "warning"
                          ? "bg-warning/10 text-warning"
                          : tone === "success"
                            ? "bg-success/10 text-success"
                            : "bg-secondary text-muted-foreground"
                    return (
                      <div
                        key={metric.key}
                        className="group relative overflow-hidden rounded-2xl border border-border bg-card/50 backdrop-blur-sm p-5 transition-all duration-300 hover:border-foreground/15 hover:shadow-lg hover:shadow-black/5"
                      >
                        <div className="flex items-center justify-between mb-4">
                          <div className={cn("flex h-10 w-10 items-center justify-center rounded-xl", iconWrap)}>
                            <metric.icon className="h-5 w-5" />
                          </div>
                          {pct !== null && (
                            <span className="text-xs font-semibold tabular-nums text-muted-foreground">{pct}%</span>
                          )}
                        </div>
                        <p className="text-3xl font-bold text-foreground tracking-tight tabular-nums">
                          {compactNumber(metric.used)}
                        </p>
                        <p className="text-xs text-muted-foreground mt-1">
                          {metric.limit
                            ? `of ${compactNumber(metric.limit)} ${metric.name.toLowerCase()}`
                            : `${metric.name.toLowerCase()} this period`}
                        </p>
                        {pct !== null && (
                          <div className="mt-4 h-2 bg-secondary rounded-full overflow-hidden">
                            <div
                              className={cn("h-full rounded-full transition-all duration-700", barClass)}
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div className="rounded-2xl border border-dashed border-border bg-card/40 p-10 text-center">
                  <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-secondary">
                    <Activity className="h-6 w-6 text-muted-foreground" />
                  </div>
                  <p className="text-sm font-medium text-foreground">No usage yet this period</p>
                  <p className="mt-1 text-sm text-muted-foreground max-w-sm mx-auto">
                    Once you start running workflows, your outputs, runs, and API activity will show up here.
                  </p>
                </div>
              )}

              {/* Outputs allowance + real overage — replaces the old fabricated forecast */}
              {hasUsage && (
                <div className="mt-4 rounded-2xl border border-border bg-card/50 backdrop-blur-sm p-6">
                  <div className="flex items-center gap-2 mb-4">
                    <TrendingUp className="h-4 w-4 text-muted-foreground" />
                    <h3 className="text-sm font-semibold text-foreground">Plan allowance</h3>
                  </div>
                  {includedOutputs === null ? (
                    <p className="text-sm text-muted-foreground">
                      Your plan includes <span className="font-medium text-foreground">unlimited outputs</span> this
                      period.
                    </p>
                  ) : (
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                      <div>
                        <p className="text-sm text-foreground">
                          <span className="font-semibold tabular-nums">
                            {compactNumber(overview?.usage?.totals.outputs ?? 0)}
                          </span>{" "}
                          of <span className="tabular-nums">{compactNumber(includedOutputs)}</span> included outputs used
                        </p>
                        {overageOutputs > 0 ? (
                          <p className="mt-1 text-sm text-warning">
                            {compactNumber(overageOutputs)} outputs over your allowance
                            {overageCost > 0 && (
                              <>
                                {" "}
                                · <span className="font-medium">{formatMoney(Math.round(overageCost * 100))}</span> in
                                overage charges
                              </>
                            )}
                          </p>
                        ) : (
                          <p className="mt-1 text-sm text-success">You&apos;re within your plan allowance.</p>
                        )}
                      </div>
                      {overageOutputs > 0 && (
                        <Button variant="outline" size="sm" onClick={() => setUpgradeModalOpen(true)}>
                          Upgrade for more
                        </Button>
                      )}
                    </div>
                  )}
                </div>
              )}
            </section>

            {/* Payment method + billing history */}
            <div className="relative z-10 grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Payment method */}
              <section className="lg:col-span-1">
                <h2 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                  <Shield className="h-4 w-4 text-muted-foreground" />
                  Payment Method
                </h2>

                <div className="rounded-2xl border border-border bg-card p-5">
                  <div className="relative mb-4 aspect-[1.6/1] rounded-xl bg-gradient-to-br from-slate-800 via-slate-900 to-slate-950 p-4 overflow-hidden">
                    <div
                      className="absolute inset-0 opacity-30"
                      style={{
                        backgroundImage: `radial-gradient(circle at 100% 0%, rgba(255,255,255,0.1) 0%, transparent 50%)`,
                      }}
                    />
                    <div className="relative h-full flex flex-col justify-between">
                      <div className="flex items-center justify-between">
                        <div className="h-8 w-10 rounded bg-gradient-to-br from-amber-300 to-amber-500 shadow-lg" />
                        <CreditCard className="h-5 w-5 text-white/60" />
                      </div>
                      {paymentMethod ? (
                        <div>
                          <p className="text-white/80 font-mono text-sm tracking-widest mb-1">
                            •••• •••• •••• {paymentMethod.last4}
                          </p>
                          <div className="flex items-center justify-between">
                            <p className="text-white/60 text-xs capitalize">{paymentMethod.type}</p>
                            <p className="text-white/60 text-xs tabular-nums">
                              {String(paymentMethod.exp_month).padStart(2, "0")}/
                              {String(paymentMethod.exp_year).slice(-2)}
                            </p>
                          </div>
                        </div>
                      ) : (
                        <p className="text-white/60 text-sm">No card on file</p>
                      )}
                    </div>
                  </div>

                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full gap-2 group"
                    onClick={openBillingPortal}
                    disabled={isProcessing}
                  >
                    {isProcessing ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <CreditCard className="h-3.5 w-3.5" />
                    )}
                    {paymentMethod ? "Manage in portal" : "Add payment method"}
                    <ChevronRight className="h-3 w-3 ml-auto transition-transform group-hover:translate-x-1" />
                  </Button>
                </div>

                <p className="mt-3 text-xs text-muted-foreground">
                  Cards and billing addresses are managed securely in the Stripe billing portal.
                </p>
              </section>

              {/* Billing history */}
              <section className="lg:col-span-2">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
                    <Clock className="h-4 w-4 text-muted-foreground" />
                    Billing History
                  </h2>
                  {invoices.length > 0 && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="gap-2 text-muted-foreground hover:text-foreground"
                      onClick={handleExportAll}
                    >
                      <Download className="h-3.5 w-3.5" />
                      Export All
                    </Button>
                  )}
                </div>

                {isLoading ? (
                  <div className="rounded-2xl border border-border overflow-hidden bg-card">
                    {[0, 1, 2].map((i) => (
                      <div key={i} className="h-16 border-b border-border last:border-0 animate-pulse bg-card/60" />
                    ))}
                  </div>
                ) : invoices.length > 0 ? (
                  <div className="rounded-2xl border border-border overflow-hidden bg-card">
                    {invoices.map((invoice, i) => {
                      const tone = invoiceStatusTone(invoice.status)
                      return (
                        <div
                          key={invoice.id}
                          className={cn(
                            "flex items-center justify-between px-5 py-4 transition-colors hover:bg-secondary/50 group",
                            i !== invoices.length - 1 && "border-b border-border",
                          )}
                        >
                          <div className="flex items-center gap-4 min-w-0">
                            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-secondary text-muted-foreground shrink-0">
                              <Receipt className="h-4 w-4" />
                            </div>
                            <div className="min-w-0">
                              <p className="text-sm font-medium text-foreground truncate">
                                {formatMoney(invoice.amount_cents, invoice.currency)}
                              </p>
                              <p className="text-xs text-muted-foreground">{formatDate(invoice.created_at)}</p>
                            </div>
                          </div>

                          <div className="flex items-center gap-3 shrink-0">
                            <span
                              className={cn(
                                "rounded-full px-2 py-0.5 text-[11px] font-medium capitalize",
                                tone.classes,
                              )}
                            >
                              {tone.label}
                            </span>
                            {invoice.pdf_url !== undefined || invoice.id ? (
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 w-8 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                                onClick={() => handleDownloadInvoice(invoice.id)}
                                aria-label="Download invoice"
                              >
                                <Download className="h-4 w-4" />
                              </Button>
                            ) : null}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <div className="rounded-2xl border border-dashed border-border bg-card/40 p-10 text-center">
                    <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-secondary">
                      <Receipt className="h-6 w-6 text-muted-foreground" />
                    </div>
                    <p className="text-sm font-medium text-foreground">No invoices yet</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Your invoices will appear here after your first billing period.
                    </p>
                  </div>
                )}
              </section>
            </div>

            {/* Support footer */}
            <div className="relative overflow-hidden rounded-2xl border border-border bg-gradient-to-br from-secondary/50 to-secondary/30 p-6">
              <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10">
                    <Sparkles className="h-5 w-5 text-emerald-500" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">Need help with billing?</p>
                    <p className="text-xs text-muted-foreground">Our support team is here to help</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Button variant="outline" size="sm" className="gap-2" asChild>
                    <a href="mailto:billing@gravitre.app">
                      <Mail className="h-3.5 w-3.5" />
                      billing@gravitre.app
                    </a>
                  </Button>
                  <Button variant="ghost" size="sm" className="gap-2" asChild>
                    <Link href="/docs">
                      <ExternalLink className="h-3.5 w-3.5" />
                      Billing FAQ
                    </Link>
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Change plan modal */}
      <Dialog open={upgradeModalOpen} onOpenChange={setUpgradeModalOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Change Your Plan</DialogTitle>
            <DialogDescription>
              Choose a plan that best fits your needs. You can upgrade or downgrade at any time.
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 py-4">
            {SELECTABLE_PLANS.map((plan) => {
              const PlanIcon = plan.icon
              const isCurrent = plan.code === currentTier
              const isSelected = selectedPlan === plan.code
              const direction = planDirection(plan.code, currentTier)
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
                      ? "border-success/50 bg-success/5 cursor-default"
                      : isSelected
                        ? "border-primary ring-2 ring-primary/30 bg-primary/5"
                        : "border-border hover:border-foreground/20 hover:-translate-y-0.5",
                  )}
                  onClick={() => !isCurrent && setSelectedPlan(plan.code)}
                >
                  {(isCurrent || plan.popular) && (
                    <span
                      className={cn(
                        "absolute -top-2 right-2 px-2 py-0.5 text-[10px] font-medium rounded-full border",
                        isCurrent
                          ? "bg-success/10 text-success border-success/20"
                          : "bg-primary/10 text-primary border-primary/20",
                      )}
                    >
                      {isCurrent ? "Current" : "Most popular"}
                    </span>
                  )}
                  <div className="flex items-center gap-2 mb-3">
                    <div
                      className={cn(
                        "h-8 w-8 rounded-lg flex items-center justify-center",
                        isCurrent ? "bg-success/10" : "bg-secondary",
                      )}
                    >
                      <PlanIcon className={cn("h-4 w-4", isCurrent ? "text-success" : "text-muted-foreground")} />
                    </div>
                    <span className="font-medium">{plan.name}</span>
                  </div>
                  <p className="text-2xl font-bold mb-3">
                    {formatPlanPrice(plan)}
                    <span className="text-sm font-normal text-muted-foreground">/mo</span>
                  </p>
                  <ul className="space-y-1.5">
                    {plan.features.map((feature, i) => (
                      <li key={i} className="text-xs text-muted-foreground flex items-center gap-2">
                        <Check className="h-3 w-3 text-success" />
                        {feature}
                      </li>
                    ))}
                  </ul>
                  {!isCurrent && (
                    <p className="mt-3 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                      {direction === "downgrade" ? "Downgrade" : "Upgrade"}
                    </p>
                  )}
                </button>
              )
            })}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setUpgradeModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => selectedPlan && handleUpgrade(selectedPlan)} disabled={!selectedPlan || isProcessing}>
              {isProcessing ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Processing...
                </>
              ) : (
                "Continue to checkout"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Cancel subscription modal */}
      <AlertDialog open={cancelModalOpen} onOpenChange={setCancelModalOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel Subscription</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to cancel your subscription? You&apos;ll keep access to all features
              {periodEndLabel ? ` until ${periodEndLabel}` : " until the end of your current billing period"}.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep Subscription</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-white hover:bg-destructive/90"
              onClick={handleCancelSubscription}
              disabled={isProcessing}
            >
              {isProcessing ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Cancelling...
                </>
              ) : (
                "Yes, Cancel"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AppShell>
  )
}
