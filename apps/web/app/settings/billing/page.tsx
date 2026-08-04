"use client"

import { useState, useEffect, useMemo, Suspense } from "react"
import useSWR from "swr"
import { motion, AnimatePresence } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { SettingsShell } from "@/components/settings/settings-shell"
import {
  MorphingBackground,
  GlowOrb,
  AnimatedCounter,
  StatusBeacon,
  ActivityIndicator
} from "@/components/gravitre/premium-effects"
import { 
  ComposedChart,
  Area, 
  Line,
  ReferenceLine,
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer
} from "recharts"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
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
  CreditCard,
  Download,
  Check,
  Zap,
  Users,
  HardDrive,
  Clock,
  ExternalLink,
  Sparkles,
  Crown,
  TrendingUp,
  Shield,
  ChevronRight,
  X,
  Loader2,
  Globe,
} from "lucide-react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { useSettingsSectionNav } from "@/lib/settings-nav"
import { billingApi, ApiRequestError } from "@/lib/api"
import { ensureSelectedOrg } from "@/lib/org-context"
import { SELECTABLE_PLANS, getPlan, formatPlanPrice, planDirection, type PlanCode } from "@/lib/plans"
import { toast } from "sonner"
import { buildUsageForecast } from "@/lib/billing-usage-forecast"
import { planLimitsFor } from "@/lib/plan-limits"

function formatInvoiceAmount(cents: number | undefined, currency = "usd") {
  if (cents == null) return "—"
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: currency.toUpperCase(),
  }).format(cents / 100)
}

/** Slot in the categorical --chart-* ramp, not a literal color name. */
type UsageMetricColor = "series1" | "series2" | "series3" | "series4"

type UsageMetric = {
  name: string
  used: number
  limit: number
  icon: typeof Zap
  color: UsageMetricColor
  /** Short unit for the “of X …” line, e.g. “credits”. */
  unit?: string
  /** Quiet clarification under the meter — never part of the big number. */
  hint?: string
  /** Optional overage / status chip. */
  note?: string
}

function emptyUsageMetrics(planCode: string): UsageMetric[] {
  const limits = planLimitsFor(planCode)
  return [
    {
      name: "Workflow Runs",
      used: 0,
      limit: Math.max(limits.workflowRuns || 1, 1),
      icon: Zap,
      color: "series1",
      unit: "runs",
    },
    {
      name: "AI Credits",
      used: 0,
      limit: Math.max(limits.aiCredits || 1, 1),
      icon: Sparkles,
      color: "series2",
      unit: "credits",
      hint: "LLM tokens only — separate from Research Lookups",
    },
  ]
}

/** Treat 0 from the API as missing so plan catalog limits still show. */
function coalesceLimit(...candidates: Array<number | null | undefined>): number {
  for (const value of candidates) {
    if (typeof value === "number" && Number.isFinite(value) && value > 0) {
      return value
    }
  }
  return 1
}

/**
 * Usage metrics are a categorical series, so they ride the themeable --chart-*
 * ramp instead of raw palette hues (one of which, purple, appeared nowhere else
 * in the product). Keys are named for the token they resolve to rather than for
 * a hardcoded color, so they can't drift from what actually renders.
 */
const colorClasses = {
  series1: {
    bg: "bg-chart-1/10",
    text: "text-chart-1",
    bar: "bg-chart-1",
    ring: "ring-chart-1/20",
    gradient: "from-chart-1/20 to-chart-1/5",
  },
  series2: {
    bg: "bg-chart-2/10",
    text: "text-chart-2",
    bar: "bg-chart-2",
    ring: "ring-chart-2/20",
    gradient: "from-chart-2/20 to-chart-2/5",
  },
  series3: {
    bg: "bg-chart-3/10",
    text: "text-chart-3",
    bar: "bg-chart-3",
    ring: "ring-chart-3/20",
    gradient: "from-chart-3/20 to-chart-3/5",
  },
  series4: {
    bg: "bg-chart-4/10",
    text: "text-chart-4",
    bar: "bg-chart-4",
    ring: "ring-chart-4/20",
    gradient: "from-chart-4/20 to-chart-4/5",
  },
}

export default function BillingPage() {
  const { isAdmin, loading: adminLoading } = useOrgAdmin()
  const onSectionChange = useSettingsSectionNav("billing")
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  return (
    <AppShell title="Settings">
      <Suspense fallback={<div className="flex h-full items-center justify-center"><div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" /></div>}>
        <SettingsShell
          activeSection="billing"
          isAdmin={isAdmin}
          mobileMenuOpen={mobileMenuOpen}
          onMobileMenuOpenChange={setMobileMenuOpen}
          onSectionChange={onSectionChange}
          hideHeader
        >
          {adminLoading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <BillingPageInner />
          )}
        </SettingsShell>
      </Suspense>
    </AppShell>
  )
}

function BillingPageInner() {
  const { user } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()
  const mounted = true
  const [animatedValues, setAnimatedValues] = useState<Record<string, number>>({})
  
  // Modal states
  const [upgradeModalOpen, setUpgradeModalOpen] = useState(false)
  const [cancelModalOpen, setCancelModalOpen] = useState(false)
  const [updateCardModalOpen, setUpdateCardModalOpen] = useState(false)
  const [editAddressModalOpen, setEditAddressModalOpen] = useState(false)
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)

  // Live subscription so the header reflects the user's actual plan instead of
  // hardcoded values. Falls back gracefully while loading / if unavailable.
  const { data: overview } = useSWR(
    user ? "billing-overview" : null,
    () => billingApi.overview(),
    { revalidateOnFocus: false },
  )
  const subscription = overview?.subscription
  // Prefer usage.tier (org_billing-backed) over subscriptions.tier, which can lag after upgrades.
  const currentTier = (
    overview?.usage?.tier ||
    subscription?.tier ||
    "node"
  ).toLowerCase() as PlanCode
  const currentPlan = getPlan(currentTier)
  const subStatus = subscription?.status ?? "active"
  const liveInvoices =
    overview?.invoices?.map((invoice) => ({
      id: invoice.id,
      date: invoice.created_at
        ? new Date(invoice.created_at).toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
            year: "numeric",
          })
        : "—",
      amount: formatInvoiceAmount(invoice.amount_cents, invoice.currency),
      status: invoice.status ? invoice.status.replace(/_/g, " ") : "—",
    })) ?? []
  const invoiceRows = liveInvoices.length > 0 ? liveInvoices : []
  const usageFromApi = overview?.usage
  const planLimits = planLimitsFor(usageFromApi?.tier ?? currentTier)
  const showResearchBilling = Boolean(usageFromApi?.research_lookups_billing_visible)
  const usageForecast = useMemo(
    () =>
      buildUsageForecast({
        overview,
        workflowLimit: usageFromApi?.workflow_runs_included ?? planLimits.workflowRuns,
        periodEndLabel: subscription?.current_period_end
          ? new Date(subscription.current_period_end).toLocaleDateString(undefined, {
              month: "short",
              day: "numeric",
            })
          : undefined,
      }),
    [overview, subscription?.current_period_end, usageFromApi?.workflow_runs_included, currentTier, planLimits.workflowRuns],
  )
  const {
    workflowUsed,
    workflowLimit: WORKFLOW_LIMIT,
    projectedTotal,
    projectedPct,
    willExceed,
    forecastSeries,
    forecastStatus,
    weeksInPeriod: WEEKS_IN_PERIOD,
  } = usageForecast
  const weeksElapsed = usageForecast.weeklyData.length
  const PERIOD_END_LABEL = forecastSeries.at(-1)?.label ?? "Period end"
  const safeBurnAt = (elapsedWeeks: number) =>
    Math.round(WORKFLOW_LIMIT * (Math.min(elapsedWeeks, WEEKS_IN_PERIOD) / WEEKS_IN_PERIOD))

  const resolvedUsageMetrics: UsageMetric[] = usageFromApi
    ? [
        {
          name: "Workflow Runs",
          used: usageFromApi.totals.workflow_runs ?? 0,
          limit: coalesceLimit(usageFromApi.workflow_runs_included, planLimits.workflowRuns),
          icon: Zap,
          color: "series1",
          unit: "runs",
        },
        {
          name: "AI Credits",
          used: usageFromApi.totals.ai_tokens ?? 0,
          limit: coalesceLimit(usageFromApi.ai_credits_included, planLimits.aiCredits),
          icon: Sparkles,
          color: "series2",
          unit: "credits",
          hint: "LLM tokens only — separate from Research Lookups",
        },
        {
          name: "Outputs",
          used: usageFromApi.totals.outputs ?? 0,
          limit: coalesceLimit(usageFromApi.included_outputs, planLimits.outputs),
          icon: HardDrive,
          color: "series3",
          unit: "outputs",
          hint: "Delivered work units included in your plan",
          note: usageFromApi.overage_outputs
            ? `${usageFromApi.overage_outputs} overage @ $${(usageFromApi.output_overage_rate_usd ?? planLimits.outputOverageUsd ?? 0).toFixed(2)}`
            : undefined,
        },
        ...(showResearchBilling
          ? [
              {
                name: "Research Lookups",
                used: usageFromApi.totals.research_lookups ?? 0,
                limit: coalesceLimit(
                  usageFromApi.included_research_lookups,
                  planLimits.researchLookups,
                ),
                icon: Globe,
                color: "series4" as const,
                unit: "lookups",
                hint: "Live internet research calls",
                note: usageFromApi.overage_research_lookups
                  ? `${usageFromApi.overage_research_lookups} overage`
                  : undefined,
              },
            ]
          : []),
      ]
    : emptyUsageMetrics(currentTier)

  const statusDisplay: Record<string, { label: string; classes: string; beacon: "active" | "warning" | "error" | "idle" }> = {
    active: { label: "Active", classes: "bg-success/10 text-success border-success/20", beacon: "active" },
    trialing: { label: "Trial", classes: "bg-info/10 text-info border-info/20", beacon: "active" },
    past_due: { label: "Past due", classes: "bg-warning/10 text-warning border-warning/20", beacon: "warning" },
    canceled: { label: "Canceled", classes: "bg-muted text-muted-foreground border-border", beacon: "idle" },
  }
  const status = statusDisplay[subStatus] ?? statusDisplay.active

  const renewalLabel = (() => {
    if (!subscription?.current_period_end) return null
    const d = new Date(subscription.current_period_end)
    if (Number.isNaN(d.getTime())) return null
    const formatted = d.toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" })
    if (subStatus === "canceled" || subscription.cancel_at_period_end) return `Access ends ${formatted}`
    if (subStatus === "trialing") return `Trial ends ${formatted}`
    return `Renews ${formatted}`
  })()
  
  // Form states
  const [cardNumber, setCardNumber] = useState("")
  const [cardExpiry, setCardExpiry] = useState("")
  const [cardCvc, setCardCvc] = useState("")
  const [cardName, setCardName] = useState("John Doe")
  const [billingAddress, setBillingAddress] = useState({
    street: "123 Market Street",
    city: "San Francisco",
    state: "CA",
    zip: "94102",
    country: "United States"
  })

  useEffect(() => {
    // Animate usage values
    const timer = setTimeout(() => {
      const values: Record<string, number> = {}
      resolvedUsageMetrics.forEach(m => {
        values[m.name] = m.used
      })
      setAnimatedValues(values)
    }, 500)
    return () => clearTimeout(timer)
  }, [])

  useEffect(() => {
    if (searchParams.get("status") === "success") {
      toast.success("Subscription activated. Full access is being restored.")
      router.replace("/settings/billing")
    }
  }, [router, searchParams])

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
    router.push(`/settings/billing/checkout?plan=${planCode}&interval=monthly`)
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
      console.error("[v0] Portal session failed:", error)
      toast.error("Failed to open billing portal")
    } finally {
      setIsProcessing(false)
      setUpdateCardModalOpen(false)
      setCardNumber("")
      setCardExpiry("")
      setCardCvc("")
    }
  }

  const handleUpdateAddress = async () => {
    setIsProcessing(true)
    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 1000))
    setIsProcessing(false)
    setEditAddressModalOpen(false)
  }

  const handleExportAll = () => {
    void (async () => {
      if (!user) {
        toast.error("Sign in required")
        return
      }
      try {
        const response = await billingApi.listInvoices()
        const csvContent =
          "Invoice ID,Amount (cents),Currency,Status,Period Start,Period End,Created At\n" +
          (response.invoices || [])
            .map(
              (inv) =>
                `${inv.id},${inv.amount_cents},${inv.currency},${inv.status},${inv.period_start},${inv.period_end},${inv.created_at}`
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

  const formatCardNumber = (value: string) => {
    const v = value.replace(/\s+/g, "").replace(/[^0-9]/gi, "")
    const matches = v.match(/\d{4,16}/g)
    const match = (matches && matches[0]) || ""
    const parts = []
    for (let i = 0, len = match.length; i < len; i += 4) {
      parts.push(match.substring(i, i + 4))
    }
    return parts.length ? parts.join(" ") : value
  }

  const formatExpiry = (value: string) => {
    const v = value.replace(/\s+/g, "").replace(/[^0-9]/gi, "")
    if (v.length >= 2) {
      return v.substring(0, 2) + "/" + v.substring(2, 4)
    }
    return v
  }

  return (
    <>
    <div className="relative overflow-hidden">
        {/* Ambient background scoped to billing content — never covers the settings rail */}
        <div className="pointer-events-none absolute inset-0 z-0 overflow-hidden">
          <div className="absolute inset-0 opacity-40">
            <MorphingBackground colors={["emerald", "blue", "violet"]} />
          </div>
          <div className="absolute inset-0 bg-gradient-to-b from-background/80 via-background/92 to-background" />
        </div>
        
        {/* Hero Header */}
        <div className="relative z-10 overflow-hidden border-b border-border/50">
          <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-chart-4/10" />
          <div className="absolute top-0 right-0 pointer-events-none">
            <GlowOrb size={280} color="emerald" intensity={0.22} />
          </div>
          <div className="absolute bottom-0 left-0 pointer-events-none">
            <GlowOrb size={220} color="violet" intensity={0.16} />
          </div>
          
          <div className="relative px-4 py-6 md:px-6 md:py-8">
              {/* Plan Overview - Premium */}
              <motion.div 
                className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
              >
                <div>
                  <div className="flex items-center gap-4 mb-2">
                    <motion.div 
                      className="relative flex h-14 w-14 items-center justify-center rounded-2xl bg-primary shadow-xl shadow-primary/30"
                      animate={{ scale: [1, 1.05, 1] }}
                      transition={{ duration: 3, repeat: Infinity }}
                    >
                      <Crown className="h-7 w-7 text-white" />
                      <motion.div 
                        className="absolute inset-0 rounded-2xl border-2 border-primary"
                        animate={{ scale: [1, 1.2], opacity: [0.6, 0] }}
                        transition={{ duration: 2, repeat: Infinity }}
                      />
                    </motion.div>
                    <div>
                      <div className="flex items-center gap-3">
                        <h1 className="text-2xl font-bold text-foreground">{currentPlan.name} Plan</h1>
                        <span className={cn(
                          "flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-full border",
                          status.classes
                        )}>
                          <StatusBeacon status={status.beacon} size="sm" pulse={subStatus === "active" || subStatus === "trialing"} />
                          {status.label}
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground mt-0.5">
                        {renewalLabel ?? currentPlan.tagline}
                      </p>
                    </div>
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
                    <Button 
                      variant="outline" 
                      size="sm" 
                      className="gap-2 group"
                      onClick={() => setUpgradeModalOpen(true)}
                    >
                      <TrendingUp className="h-3.5 w-3.5 transition-transform group-hover:-translate-y-0.5" />
                      Upgrade Plan
                    </Button>
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="text-xs text-muted-foreground"
                      onClick={() => setCancelModalOpen(true)}
                    >
                      Cancel Subscription
                    </Button>
                  </div>
                </div>
              </motion.div>
          </div>
        </div>

        {/* Main Content */}
        <div className="relative z-10 space-y-10 px-4 py-6 md:px-6 md:py-8">
            {/* Usage Metrics */}
            <section className={cn(
              "transition-all duration-500 delay-200",
              mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
            )}>
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-muted-foreground" />
                  <h2 className="text-sm font-semibold text-foreground">Current Usage</h2>
                </div>
                <span className="text-xs text-muted-foreground">
                  {subscription?.current_period_end
                    ? `Period ends ${new Date(subscription.current_period_end).toLocaleDateString(undefined, { month: "short", day: "numeric" })}`
                    : "Current billing period"}
                </span>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {resolvedUsageMetrics.map((metric, i) => {
                  const percentage =
                    metric.limit > 0 ? Math.min(100, (metric.used / metric.limit) * 100) : 0
                  const colors = colorClasses[metric.color]
                  const displayValue = animatedValues[metric.name] ?? 0
                  const pctLabel = metric.limit > 0 ? `${Math.round(percentage)}%` : "—"

                  return (
                    <div
                      key={metric.name}
                      className={cn(
                        "relative flex flex-col rounded-2xl border border-border/70 bg-card/80 p-4 transition-opacity duration-500",
                        mounted ? "opacity-100" : "opacity-0",
                      )}
                      style={{ transitionDelay: `${200 + i * 60}ms` }}
                    >
                      <div className="mb-3 flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <div className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-lg", colors.bg)}>
                              <metric.icon className={cn("h-4 w-4", colors.text)} />
                            </div>
                            <p className="truncate text-sm font-medium text-foreground">{metric.name}</p>
                          </div>
                        </div>
                        <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{pctLabel}</span>
                      </div>

                      <div className="mb-3 flex items-baseline gap-1.5">
                        <p className="text-2xl font-semibold tracking-tight text-foreground tabular-nums">
                          {displayValue.toLocaleString()}
                        </p>
                        <p className="text-sm text-muted-foreground tabular-nums">
                          / {metric.limit.toLocaleString()}
                          {metric.unit ? ` ${metric.unit}` : ""}
                        </p>
                      </div>

                      <div className="mt-auto h-1.5 overflow-hidden rounded-full bg-muted/80">
                        <div
                          className={cn(
                            "h-full rounded-full transition-all duration-700 ease-out",
                            // Near-quota is a genuine health signal, so it
                            // overrides the categorical series color.
                            percentage >= 90 ? "bg-warning" : colors.bar,
                          )}
                          style={{
                            width: mounted ? `${Math.min(percentage, 100)}%` : "0%",
                            transitionDelay: `${350 + i * 60}ms`,
                          }}
                        />
                      </div>

                      {metric.note ? (
                        <p className="mt-2 text-[11px] font-medium text-warning">
                          {metric.note}
                        </p>
                      ) : null}
                      {metric.hint ? (
                        <p className="mt-2 text-[11px] leading-snug text-muted-foreground">{metric.hint}</p>
                      ) : null}
                    </div>
                  )
                })}
              </div>
            </section>

            {/* Usage trajectory — projected against plan allowance */}
            <motion.section
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              className="relative"
            >
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <h2 className="text-sm font-semibold text-foreground">Usage trajectory</h2>
                    <p className="text-xs text-muted-foreground">Projected against your plan allowance for this billing period.</p>
                  </div>
                </div>
                <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium", forecastStatus.soft, forecastStatus.accent)}>
                  <span className={cn("h-1.5 w-1.5 rounded-full", forecastStatus.dot)} />
                  {forecastStatus.label}
                </span>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
                {/* Projection chart */}
                <div className="relative rounded-2xl border border-border bg-card/50 backdrop-blur-sm p-6 overflow-hidden lg:col-span-3">
                  <div className="absolute top-0 right-0 w-32 h-32 pointer-events-none">
                    <GlowOrb size={100} color="emerald" intensity={0.2} />
                  </div>
                  <div className="flex items-end justify-between mb-4">
                    <div>
                      <h3 className="text-xs font-medium text-muted-foreground">Workflow runs · this period</h3>
                      <p className="mt-1 text-2xl font-bold text-foreground tabular-nums">
                        {projectedTotal.toLocaleString()}
                        <span className="ml-1.5 text-sm font-normal text-muted-foreground">projected of {WORKFLOW_LIMIT.toLocaleString()}</span>
                      </p>
                    </div>
                    <p className={cn("text-sm font-semibold tabular-nums", forecastStatus.accent)}>{projectedPct}%</p>
                  </div>
                  <div className="h-[200px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart data={forecastSeries} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                        <defs>
                          <linearGradient id="forecastActual" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="var(--success)" stopOpacity={0.25} />
                            <stop offset="95%" stopColor="var(--success)" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.4} vertical={false} />
                        <XAxis dataKey="label" stroke="var(--muted-foreground)" fontSize={10} tickLine={false} axisLine={false} />
                        <YAxis stroke="var(--muted-foreground)" fontSize={10} tickLine={false} axisLine={false} width={36}
                          tickFormatter={(v) => (Number(v) >= 1000 ? `${Math.round(Number(v) / 1000)}k` : `${v}`)} />
                        <Tooltip
                          formatter={(value) => (typeof value === "number" ? value.toLocaleString() : value)}
                          contentStyle={{ backgroundColor: 'var(--card)', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '12px' }}
                        />
                        <ReferenceLine y={WORKFLOW_LIMIT} stroke="var(--warning)" strokeDasharray="4 4"
                          label={{ value: `Plan limit ${(WORKFLOW_LIMIT / 1000)}k`, position: 'insideTopRight', fontSize: 10, fill: 'var(--warning)' }} />
                        <Line type="monotone" dataKey="safe" name="Safe pace" stroke="var(--info)" strokeWidth={1.5} strokeDasharray="2 3" dot={false} opacity={0.7} />
                        <Area type="monotone" dataKey="actual" name="Actual" stroke="var(--success)" strokeWidth={2.5} fill="url(#forecastActual)" connectNulls={false} dot={{ r: 2 }} />
                        <Line type="monotone" dataKey="projected" stroke="var(--muted-foreground)" strokeWidth={2} strokeDasharray="5 4" dot={{ r: 3 }} connectNulls />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
                    <span className="flex items-center gap-1.5"><span className="h-0.5 w-3 rounded-full bg-success" />Actual</span>
                    <span className="flex items-center gap-1.5"><span className="h-0.5 w-3 rounded-full bg-info opacity-70" />Safe pace</span>
                    <span className="flex items-center gap-1.5"><span className="h-0.5 w-3 rounded-full bg-muted-foreground" />Projected</span>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">
                    {willExceed
                      ? `You're burning above the safe pace — at your recent rate you'll pass the ${WORKFLOW_LIMIT.toLocaleString()} limit before ${PERIOD_END_LABEL}.`
                      : `You're tracking ${workflowUsed <= safeBurnAt(weeksElapsed) ? "under" : "near"} the safe pace — about ${projectedTotal.toLocaleString()} runs by ${PERIOD_END_LABEL}${WORKFLOW_LIMIT - projectedTotal > 0 ? `, ${(WORKFLOW_LIMIT - projectedTotal).toLocaleString()} to spare.` : ", right at the limit."}`}
                  </p>
                </div>

                {/* Closest to limit — which resource is the binding constraint */}
                <div className="relative rounded-2xl border border-border bg-card/50 backdrop-blur-sm p-6 overflow-hidden lg:col-span-2">
                  <h3 className="text-xs font-medium text-muted-foreground mb-4">Closest to limit</h3>
                  <div className="space-y-4">
                    {[...resolvedUsageMetrics]
                      .map((m) => ({
                        ...m,
                        pct: m.limit > 0 ? Math.round((m.used / m.limit) * 100) : 0,
                      }))
                      .sort((a, b) => b.pct - a.pct)
                      .map((m, i) => {
                        const tone = m.pct >= 85 ? "destructive" : m.pct >= 60 ? "warning" : "success"
                        const bar = tone === "destructive" ? "bg-destructive" : tone === "warning" ? "bg-warning" : "bg-success"
                        const text = tone === "destructive" ? "text-destructive" : tone === "warning" ? "text-warning" : "text-success"
                        return (
                          <div key={m.name}>
                            <div className="flex items-center justify-between text-xs mb-1.5">
                              <span className="flex items-center gap-1.5 text-foreground">
                                <m.icon className="h-3.5 w-3.5 text-muted-foreground" />
                                {m.name}
                                {i === 0 && <span className="ml-1 rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">tightest</span>}
                              </span>
                              <span className={cn("font-semibold tabular-nums", text)}>{m.pct}%</span>
                            </div>
                            <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                              <div className={cn("h-full rounded-full transition-all", bar)} style={{ width: `${Math.min(100, m.pct)}%` }} />
                            </div>
                          </div>
                        )
                      })}
                  </div>
                  <p className="mt-4 text-xs text-muted-foreground">Percent of each plan allowance used this period.</p>
                </div>
              </div>
            </motion.section>

            {/* Payment Method & Billing History */}
            <div className="relative z-10 grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Payment Method */}
              <section className={cn(
                "lg:col-span-1 transition-all duration-500 delay-400",
                mounted ? "opacity-100 translate-x-0" : "opacity-0 -translate-x-8"
              )}>
                <h2 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                  <Shield className="h-4 w-4 text-muted-foreground" />
                  Payment Method
                </h2>
                
                <div className="group relative overflow-hidden rounded-2xl border border-border bg-card p-5 transition-all duration-300 hover:shadow-lg hover:shadow-black/5">
                  {/* Card visual */}
                  <div className="relative mb-4 aspect-[1.6/1] rounded-xl bg-gradient-to-br from-slate-800 via-slate-900 to-slate-950 p-4 overflow-hidden">
                    {/* Card pattern */}
                    <div className="absolute inset-0 opacity-30" style={{
                      backgroundImage: `radial-gradient(circle at 100% 0%, rgba(255,255,255,0.1) 0%, transparent 50%)`,
                    }} />
                    <div className="absolute bottom-0 left-0 right-0 h-20 bg-gradient-to-t from-black/20 to-transparent" />
                    
                    <div className="relative h-full flex flex-col justify-between">
                      <div className="flex items-center justify-between">
                        <div className="h-8 w-10 rounded bg-gradient-to-br from-amber-300 to-amber-500 shadow-lg" />
                        <span className="text-xs text-white/60 font-medium">VISA</span>
                      </div>
                      <div>
                        <p className="text-white/80 font-mono text-sm tracking-widest mb-1">
                          •••• •••• •••• 4242
                        </p>
                        <div className="flex items-center justify-between">
                          <p className="text-white/60 text-xs">John Doe</p>
                          <p className="text-white/60 text-xs">12/25</p>
                        </div>
                      </div>
                    </div>
                  </div>

                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="w-full gap-2 group"
                    onClick={() => setUpdateCardModalOpen(true)}
                  >
                    <CreditCard className="h-3.5 w-3.5" />
                    Update Card
                    <ChevronRight className="h-3 w-3 ml-auto transition-transform group-hover:translate-x-1" />
                  </Button>
                </div>

                {/* Billing address quick link */}
                <div className="mt-4 p-4 rounded-xl border border-dashed border-border bg-secondary/30">
                  <p className="text-xs text-muted-foreground mb-2">Billing Address</p>
                  <p className="text-sm text-foreground">{billingAddress.street}</p>
                  <p className="text-sm text-foreground">{billingAddress.city}, {billingAddress.state} {billingAddress.zip}</p>
                  <Button 
                    variant="link" 
                    size="sm" 
                    className="h-auto p-0 mt-2 text-xs"
                    onClick={() => setEditAddressModalOpen(true)}
                  >
                    Edit address
                  </Button>
                </div>
              </section>

              {/* Billing History */}
              <section className={cn(
                "lg:col-span-2 transition-all duration-500 delay-500",
                mounted ? "opacity-100 translate-x-0" : "opacity-0 translate-x-8"
              )}>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
                    <Clock className="h-4 w-4 text-muted-foreground" />
                    Billing History
                  </h2>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="gap-2 text-muted-foreground hover:text-foreground"
                    onClick={handleExportAll}
                  >
                    <Download className="h-3.5 w-3.5" />
                    Export All
                  </Button>
                </div>

                <div className="rounded-2xl border border-border overflow-hidden bg-card">
                  {invoiceRows.length === 0 ? (
                    <div className="px-5 py-10 text-center text-sm text-muted-foreground">
                      No invoices yet. Your billing history will appear here after your first payment.
                    </div>
                  ) : (
                  invoiceRows.map((invoice, i) => (
                    <div 
                      key={invoice.id}
                      className={cn(
                        "flex items-center justify-between px-5 py-4 transition-all duration-300 hover:bg-secondary/50 group",
                        i !== invoiceRows.length - 1 && "border-b border-border"
                      )}
                    >
                      <div className="flex items-center gap-4">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-secondary group-hover:bg-success/10 transition-colors">
                          <Check className="h-4 w-4 text-success" />
                        </div>
                        <div>
                          <p className="text-sm font-mono text-foreground">{invoice.id}</p>
                          <p className="text-xs text-muted-foreground">{invoice.date}</p>
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-4">
                        <span className="text-sm font-semibold text-foreground">{invoice.amount}</span>
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          className="h-8 w-8 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={() => handleDownloadInvoice(invoice.id)}
                        >
                          <Download className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  ))
                  )}
                </div>

                <p className="text-xs text-muted-foreground mt-4 text-center">
                  Need older invoices?{" "}
                  <Link href="/support" className="text-foreground hover:underline">
                    Contact support
                  </Link>
                </p>
              </section>
            </div>

            {/* Footer */}
            <div className={cn(
              "relative overflow-hidden rounded-2xl border border-border bg-gradient-to-br from-secondary/50 to-secondary/30 p-6 transition-all duration-500 delay-600",
              mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
            )}>
              <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
                    <Sparkles className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">Need help with billing?</p>
                    <p className="text-xs text-muted-foreground">Our support team is available 24/7</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Button variant="outline" size="sm" className="gap-2">
                    <Mail className="h-3.5 w-3.5" />
                    billing@gravitre.app
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

      {/* Upgrade Plan Modal */}
      <Dialog open={upgradeModalOpen} onOpenChange={setUpgradeModalOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Upgrade Your Plan</DialogTitle>
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
                        : "border-border hover:border-foreground/20 hover:-translate-y-0.5"
                  )}
                  onClick={() => !isCurrent && setSelectedPlan(plan.code)}
                >
                  {(isCurrent || plan.popular) && (
                    <span className={cn(
                      "absolute -top-2 right-2 px-2 py-0.5 text-[10px] font-medium rounded-full border",
                      isCurrent
                        ? "bg-success/10 text-success border-success/20"
                        : "bg-primary/10 text-primary border-primary/20"
                    )}>
                      {isCurrent ? "Current" : "Most popular"}
                    </span>
                  )}
                  <div className="flex items-center gap-2 mb-3">
                    <div className={cn(
                      "h-8 w-8 rounded-lg flex items-center justify-center",
                      isCurrent ? "bg-success/10" : "bg-secondary"
                    )}>
                      <PlanIcon className={cn("h-4 w-4", isCurrent ? "text-success" : "text-muted-foreground")} />
                    </div>
                    <span className="font-medium">{plan.name}</span>
                  </div>
                  <p className="text-2xl font-bold mb-3">{formatPlanPrice(plan)}<span className="text-sm font-normal text-muted-foreground">/mo</span></p>
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
            <Button 
              onClick={() => selectedPlan && handleUpgrade(selectedPlan)}
              disabled={!selectedPlan}
            >
              Upgrade Plan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Cancel Subscription Modal */}
      <AlertDialog open={cancelModalOpen} onOpenChange={setCancelModalOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel Subscription</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to cancel your subscription? You will lose access to all premium features at the end of your current billing period (May 1, 2024).
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

      {/* Update Card Modal */}
      <Dialog open={updateCardModalOpen} onOpenChange={setUpdateCardModalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Update Payment Method</DialogTitle>
            <DialogDescription>
              Enter your new card details below. Your card will be charged for future billing cycles.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="cardName">Name on Card</Label>
              <Input
                id="cardName"
                placeholder="John Doe"
                value={cardName}
                onChange={(e) => setCardName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="cardNumber">Card Number</Label>
              <Input
                id="cardNumber"
                placeholder="4242 4242 4242 4242"
                value={cardNumber}
                onChange={(e) => setCardNumber(formatCardNumber(e.target.value))}
                maxLength={19}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="expiry">Expiry Date</Label>
                <Input
                  id="expiry"
                  placeholder="MM/YY"
                  value={cardExpiry}
                  onChange={(e) => setCardExpiry(formatExpiry(e.target.value))}
                  maxLength={5}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="cvc">CVC</Label>
                <Input
                  id="cvc"
                  placeholder="123"
                  value={cardCvc}
                  onChange={(e) => setCardCvc(e.target.value.replace(/\D/g, "").slice(0, 4))}
                  maxLength={4}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setUpdateCardModalOpen(false)}>
              Cancel
            </Button>
            <Button 
              onClick={handleUpdateCard}
              disabled={isProcessing || !cardNumber || !cardExpiry || !cardCvc}
            >
              {isProcessing ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Updating...
                </>
              ) : (
                "Update Card"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Address Modal */}
      <Dialog open={editAddressModalOpen} onOpenChange={setEditAddressModalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Edit Billing Address</DialogTitle>
            <DialogDescription>
              Update your billing address for invoices and receipts.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="street">Street Address</Label>
              <Input
                id="street"
                value={billingAddress.street}
                onChange={(e) => setBillingAddress({...billingAddress, street: e.target.value})}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="city">City</Label>
                <Input
                  id="city"
                  value={billingAddress.city}
                  onChange={(e) => setBillingAddress({...billingAddress, city: e.target.value})}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="state">State</Label>
                <Input
                  id="state"
                  value={billingAddress.state}
                  onChange={(e) => setBillingAddress({...billingAddress, state: e.target.value})}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="zip">ZIP Code</Label>
                <Input
                  id="zip"
                  value={billingAddress.zip}
                  onChange={(e) => setBillingAddress({...billingAddress, zip: e.target.value})}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="country">Country</Label>
                <Input
                  id="country"
                  value={billingAddress.country}
                  onChange={(e) => setBillingAddress({...billingAddress, country: e.target.value})}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditAddressModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleUpdateAddress} disabled={isProcessing}>
              {isProcessing ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                "Save Address"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

function Mail({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect width="20" height="16" x="2" y="4" rx="2"/>
      <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>
    </svg>
  )
}
