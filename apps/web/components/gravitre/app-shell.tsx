"use client"

import { useState, useEffect, startTransition } from "react"
import useSWR, { mutate } from "swr"
import Link from "next/link"
import { Sidebar } from "./sidebar"
import { TopBar } from "./top-bar"
import { CommandPalette } from "./command-palette"
import { GoalWorkflowWizard } from "./goal-workflow-wizard"
import { usePathname, useRouter } from "next/navigation"
import { useAuth } from "@/lib/auth-context"
import { useEnterpriseBranding } from "@/lib/enterprise-branding-context"
import { clearAuthTransition } from "@/lib/auth-transition"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useGlobalWorkShortcuts } from "@/hooks/use-global-work-shortcuts"
import { onboardingApi } from "@/lib/api"
import { Loader2, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { TrialExpiredBanner } from "@/components/billing/trial-expired-banner"
import { UpgradeModal } from "@/components/billing/upgrade-modal"
import {
  PLAN_REQUIRED_EVENT,
  readStoredPlanRequired,
  clearStoredPlanRequired,
  type PlanRequiredDetail,
} from "@/lib/billing-plan-required"

interface AppShellProps {
  children: React.ReactNode
  title?: string
}

interface BillingStatus {
  billingStatus?: string
  planCode?: string
  canAccessApp?: boolean
  requiresUpgrade?: boolean
  upgradeReason?: string | null
  trialEndsAt?: string | null
  currentPeriodEnd?: string | null
  cancelAtPeriodEnd?: boolean
  trialExpired?: boolean
  billingState?: string
}

interface MeData {
  org_id?: string
  onboarding?: {
    seeded?: boolean
    completed_at?: string | null
    checklist_dismissed?: boolean
  }
  billing?: {
    status?: string
    plan_code?: string
    can_access_app?: boolean
    trial_ends_at?: string | null
  }
}

// Calculate days left in trial
function daysLeft(isoDate: string): number {
  const now = new Date()
  const end = new Date(isoDate)
  const diff = end.getTime() - now.getTime()
  return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)))
}

export function AppShell({ children, title }: AppShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [goalWizardOpen, setGoalWizardOpen] = useState(false)
  const [trialBannerDismissed, setTrialBannerDismissed] = useState(
    () =>
      typeof window !== "undefined" &&
      sessionStorage.getItem("gravitre-trial-banner-dismissed") === "true",
  )
  const [welcomeDismissed, setWelcomeDismissed] = useState(
    () =>
      typeof window !== "undefined" &&
      localStorage.getItem("gravitre-welcome-dismissed") === "true",
  )
  const [bootstrapAttempted, setBootstrapAttempted] = useState(false)
  const [upgradeModalOpen, setUpgradeModalOpen] = useState(false)
  const [planRequired, setPlanRequired] = useState<PlanRequiredDetail | null>(null)
  const router = useRouter()
  const pathname = usePathname()
  const { user, loading } = useAuth()
  const { effectiveHidePoweredBy } = useEnterpriseBranding()

  useGlobalWorkShortcuts()

  // Fetch billing status (no polling — avoids periodic shell revalidation)
  const { data: billingStatusData, isLoading: billingLoading, error: billingError } = useSWR<BillingStatus>(
    user ? "/api/billing/status" : null,
    apiFetcher,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
      dedupingInterval: 60_000,
    }
  )

  // Fetch auth/me for onboarding status
  const { data: meData } = useSWR<MeData>(
    user ? "/api/auth/me" : null,
    apiFetcher,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
      dedupingInterval: 60_000,
    }
  )

  const billingAccessDenied =
    billingStatusData !== undefined && billingStatusData.canAccessApp === false
  const billingStatus = String(billingStatusData?.billingStatus ?? "inactive").toLowerCase()
  const trialEndsAt = billingStatusData?.trialEndsAt
  const requiresUpgrade = billingStatusData?.requiresUpgrade ?? false
  const trialExpired =
    billingStatusData?.trialExpired === true ||
    billingStatusData?.billingState === "trial_expired" ||
    billingStatusData?.upgradeReason === "trial_expired" ||
    planRequired?.subscription_status === "trial_expired"
  const billingHardBlock =
    billingAccessDenied && !trialExpired
  const canAccessApp =
    billingStatusData?.canAccessApp ??
    meData?.billing?.can_access_app ??
    !billingAccessDenied

  useEffect(() => {
    setPlanRequired(readStoredPlanRequired())
    const handler = (event: Event) => {
      const detail = (event as CustomEvent<PlanRequiredDetail>).detail
      setPlanRequired(detail)
      setUpgradeModalOpen(true)
    }
    window.addEventListener(PLAN_REQUIRED_EVENT, handler)
    return () => window.removeEventListener(PLAN_REQUIRED_EVENT, handler)
  }, [])

  useEffect(() => {
    if (canAccessApp && billingStatusData?.canAccessApp !== false) {
      clearStoredPlanRequired()
      setPlanRequired(null)
    }
  }, [canAccessApp, billingStatusData?.canAccessApp])

  // Auto-bootstrap for OAuth users who skip /get-started
  useEffect(() => {
    if (!user || !canAccessApp || !meData || bootstrapAttempted) return
    if (meData.onboarding?.seeded === true) return

    startTransition(() => setBootstrapAttempted(true))

    void (async () => {
      try {
        await onboardingApi.bootstrap()
        // Revalidate auth/me so welcome banner can read seeded: true
        mutate("/api/auth/me")
      } catch (err) {
        console.warn("Demo bootstrap failed", err)
        // Non-blocking — user still sees app
      }
    })()
  }, [user, canAccessApp, meData, bootstrapAttempted])

  // Handle trial banner dismiss
  const handleDismissTrialBanner = () => {
    setTrialBannerDismissed(true)
    if (typeof window !== "undefined") {
      sessionStorage.setItem("gravitre-trial-banner-dismissed", "true")
    }
  }

  // Handle welcome banner dismiss
  const handleDismissWelcome = () => {
    setWelcomeDismissed(true)
    if (typeof window !== "undefined") {
      localStorage.setItem("gravitre-welcome-dismissed", "true")
    }
  }

  // Clear OAuth transition grace period once the shell has a signed-in user.
  useEffect(() => {
    if (!user && !loading) {
      clearAuthTransition()
      return
    }
    if (user) {
      clearAuthTransition()
    }
  }, [user, loading])

  // Send unauthenticated visitors to login once (avoid infinite spinner).
  useEffect(() => {
    if (loading || user) return
    router.replace("/login?intent=login")
  }, [loading, user, router])

  // Hard redirect only for non-trial blocks (e.g. canceled). Expired trials stay in
  // the product shell so the non-dismissible banner and 402 upgrade modal can surface.
  useEffect(() => {
    if (!billingHardBlock || billingError) return
    if (pathname.startsWith("/settings/billing") || pathname.startsWith("/pricing")) return
    router.replace("/settings/billing?reason=subscription_required")
  }, [billingHardBlock, billingError, pathname, router])

  const showTrialExpiredBanner =
    trialExpired ||
    planRequired?.subscription_status === "trial_expired"

  // Show loading only on the first auth/billing bootstrap — not on background revalidation.
  const awaitingInitialBilling = Boolean(user) && billingLoading && billingStatusData === undefined
  if (loading || awaitingInitialBilling) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  if (!user) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  if (billingHardBlock && !billingError && !pathname.startsWith("/settings/billing") && !pathname.startsWith("/pricing")) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  // If billing API errored, log warning but allow through (fail open)
  if (billingError) {
    console.warn("Billing API error, allowing access:", billingError)
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
        <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <div className="flex flex-1 flex-col overflow-hidden">
          <TopBar title={title} onMenuClick={() => setSidebarOpen(true)} />

          {showTrialExpiredBanner && (
            <TrialExpiredBanner
              message={planRequired?.message}
              upgradeUrl={planRequired?.upgrade_url ?? "/settings/billing"}
              onUpgradeClick={() => setUpgradeModalOpen(true)}
            />
          )}
          
          {/* Trial Banner (active trial only — not after expiry) */}
          {billingStatus === "trialing" && !trialExpired && !trialBannerDismissed && (() => {
            const days = trialEndsAt ? daysLeft(trialEndsAt) : null
            const urgent = days !== null && days <= 3
            const warning = days !== null && days <= 7
            const bannerClass = urgent
              ? "border-destructive/30 bg-destructive/10 text-foreground"
              : warning
                ? "border-warning/30 bg-warning/10 text-foreground"
                : "border-success/30 bg-success/10 text-foreground"
            return (
            <div className={cn("border-b px-4 py-2 text-sm flex items-center justify-between", bannerClass)} data-testid="active-trial-banner">
              <span>
                You&apos;re on a 7-day free trial of Node.
                {days !== null && ` ${days} day${days === 1 ? "" : "s"} left.`}
                {" "}
                {urgent ? (
                  <Link href="/pricing" className="underline font-semibold hover:opacity-80">
                    Upgrade now
                  </Link>
                ) : (
                  <Link href="/pricing" className="underline font-medium hover:opacity-80">
                    View plans
                  </Link>
                )}
              </span>
              <button 
                onClick={handleDismissTrialBanner} 
                aria-label="Dismiss trial banner"
                className="p-1 hover:bg-black/5 rounded transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            )
          })()}

          {/* Upgrade Nudge for past_due users */}
          {requiresUpgrade && canAccessApp && billingStatus === "past_due" && (
            <div className="border-b border-warning/30 bg-warning/10 px-4 py-2 text-sm text-foreground flex items-center justify-between">
              <span>
                Your payment needs attention.{" "}
                <Link href="/settings/billing" className="underline font-medium hover:opacity-80">
                  Update billing
                </Link>
                {" "}to avoid interruption.
              </span>
            </div>
          )}

          {/* Welcome Banner (after bootstrap) */}
          {meData?.onboarding?.seeded && !welcomeDismissed && (
            <div className="border-b border-success/30 bg-success/10 px-4 py-3 text-sm text-foreground">
              <div className="flex items-start justify-between gap-4 max-w-4xl mx-auto">
                <div>
                  <p className="font-medium">Welcome to Gravitre!</p>
                  <p className="text-muted-foreground">
                    We&apos;ve set up a sample AI team to show you what&apos;s possible.
                    These are demo agents — connect your real tools to activate them.
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <Link href="/agents">
                    <Button size="sm" variant="default">Explore agents</Button>
                  </Link>
                  <button 
                    onClick={handleDismissWelcome} 
                    aria-label="Dismiss welcome banner"
                    className="p-1 hover:bg-success/20 rounded transition-colors"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          )}

          <main className="flex-1 overflow-y-auto">{children}</main>

          {/* White-label footer - hidden when org sets hidePoweredBy */}
          {!effectiveHidePoweredBy && (
            <footer className="border-t border-border px-4 py-2 text-center">
              <span className="text-[11px] text-muted-foreground/60">
                Powered by{" "}
                <a
                  href="https://gravitre.ai"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-muted-foreground/80 hover:text-foreground transition-colors"
                >
                  Gravitre
                </a>
              </span>
            </footer>
          )}
        </div>
      
      {/* Command Palette - accessible via Cmd+K */}
      <CommandPalette onCreateFromGoal={() => setGoalWizardOpen(true)} />
      
      {/* Goal Workflow Wizard */}
      <GoalWorkflowWizard
        open={goalWizardOpen}
        onOpenChange={setGoalWizardOpen}
        onBuildWorkflow={(plan) => {
          console.log("Goal plan:", plan)
          router.push("/workflows/new/builder")
        }}
      />
      <UpgradeModal
        open={upgradeModalOpen}
        onOpenChange={setUpgradeModalOpen}
        subscriptionStatus={planRequired?.subscription_status ?? billingStatusData?.billingState}
      />
    </div>
  )
}
