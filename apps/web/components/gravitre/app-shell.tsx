"use client"

import { useState, useEffect, startTransition, useCallback } from "react"
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
import { APP_ROUTES } from "@/lib/app-routes"
import { Loader2, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { AppBreadcrumbs } from "./app-breadcrumbs"
import type { OnboardingProgress } from "@/types/api"
import { TrialExpiredBanner } from "@/components/billing/trial-expired-banner"
import { UpgradeModal } from "@/components/billing/upgrade-modal"
import { MesonToolbarPopup, MesonToolbarProvider } from "@/components/gravitre/meson-toolbar-popup"
import {
  PLAN_REQUIRED_EVENT,
  readStoredPlanRequired,
  clearStoredPlanRequired,
  emitPlanRequired,
  type PlanRequiredDetail,
} from "@/lib/billing-plan-required"
import {
  isBillingStatusDegraded,
  isTrialExpiredState,
  resolveCanAccessApp,
  trialExpiredBannerMessage,
  type BillingStatusSnapshot,
} from "@/lib/billing-trial-state"

interface AppShellProps {
  children: React.ReactNode
  title?: string
  /** Vendor key shown beside connector detail breadcrumbs. */
  breadcrumbVendor?: string
}

interface BillingStatus extends BillingStatusSnapshot {
  currentPeriodEnd?: string | null
  cancelAtPeriodEnd?: boolean
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
    can_access_app?: boolean | null
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

export function AppShell({ children, title, breadcrumbVendor }: AppShellProps) {
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
  const isImmersiveChat = pathname === "/ai" || pathname.startsWith("/ai/")
  const { user, loading } = useAuth()
  const { effectiveHidePoweredBy } = useEnterpriseBranding()

  useGlobalWorkShortcuts()

  // Menu button only opens the mobile drawer — desktop nav is always visible.
  const handleMenuClick = useCallback(() => setSidebarOpen(true), [])
  const closeSidebar = useCallback(() => setSidebarOpen(false), [])

  // Close shell overlays on route change so remount races cannot leave
  // full-viewport dialogs / scroll-locks blocking sidebar navigation.
  useEffect(() => {
    setSidebarOpen(false)
    setGoalWizardOpen(false)
    setUpgradeModalOpen(false)
  }, [pathname])

  // Fetch billing status — refresh on focus so web/mobile stay aligned after expiry.
  const { data: billingStatusData, isLoading: billingLoading, error: billingError } = useSWR<BillingStatus>(
    user ? "/api/billing/status" : null,
    apiFetcher,
    {
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 30_000,
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

  const { data: onboardingProgress } = useSWR<OnboardingProgress>(
    user ? "/api/onboarding" : null,
    apiFetcher,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
      dedupingInterval: 60_000,
    },
  )

  const billingAccessDenied =
    billingStatusData !== undefined && billingStatusData.canAccessApp === false
  const billingStatus = String(billingStatusData?.billingStatus ?? "inactive").toLowerCase()
  const trialEndsAt = billingStatusData?.trialEndsAt
  const requiresUpgrade = billingStatusData?.requiresUpgrade ?? false
  const trialExpired = isTrialExpiredState(billingStatusData, planRequired)
  const billingHardBlock =
    billingAccessDenied && !trialExpired
  const canAccessApp = resolveCanAccessApp(
    billingStatusData,
    meData?.billing?.can_access_app,
    planRequired,
  )

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
    if (isBillingStatusDegraded(billingStatusData) || trialExpired) return
    if (billingStatusData?.canAccessApp !== true) return
    clearStoredPlanRequired()
    setPlanRequired(null)
  }, [billingStatusData, trialExpired])

  useEffect(() => {
    if (isBillingStatusDegraded(billingStatusData)) return
    if (!isTrialExpiredState(billingStatusData, null)) return
    emitPlanRequired(
      {
        error: "plan_required",
        subscription_status: "trial_expired",
        message: "Your 7-day trial has ended. Upgrade to continue using Gravitre.",
        upgrade_url: "/settings/billing",
      },
      { dispatchEvent: false },
    )
    setPlanRequired(readStoredPlanRequired())
  }, [billingStatusData])

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

  // First-run welcome flow — only gate the home entry surface, not every sidebar navigation.
  useEffect(() => {
    if (!user || !onboardingProgress) return
    if (!canAccessApp) return
    const exemptPrefixes = [
      "/welcome",
      "/login",
      "/get-started",
      "/auth/",
      "/settings/billing",
      "/pricing",
      "/onboarding",
    ]
    if (exemptPrefixes.some((prefix) => pathname.startsWith(prefix))) return
    if (onboardingProgress.welcome_completed || onboardingProgress.skipped) return

    const isWelcomeGateEntry = pathname === APP_ROUTES.home || pathname === "/"
    if (!isWelcomeGateEntry) return

    router.replace(APP_ROUTES.welcome)
  }, [user, onboardingProgress, pathname, router, canAccessApp])

  const showTrialExpiredBanner = trialExpired

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
    <MesonToolbarProvider>
    <div className="relative h-screen overflow-hidden bg-background">
    <div className="grid h-full grid-cols-1 overflow-hidden md:grid-cols-[auto_minmax(0,1fr)]">
        <Sidebar isOpen={sidebarOpen} onClose={closeSidebar} />
        <div className="relative z-0 flex min-w-0 flex-col overflow-hidden">
          <TopBar title={title} onMenuClick={handleMenuClick} />

          {showTrialExpiredBanner && (
            <TrialExpiredBanner
              message={trialExpiredBannerMessage(planRequired)}
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
                    We&apos;ve set up a starter AI team from your role pack. Connect your tools to activate live execution.
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

          <main
            className={cn(
              "flex min-h-0 flex-1 flex-col",
              isImmersiveChat ? "overflow-hidden pb-0" : "overflow-y-auto pb-20",
            )}
          >
            {!isImmersiveChat ? (
              <div className="px-4 pt-3 md:px-6">
                <AppBreadcrumbs entityLabel={title} entityVendor={breadcrumbVendor} />
              </div>
            ) : null}
            {children}
          </main>

          {/* White-label footer - hidden when org sets hidePoweredBy or on immersive chat */}
          {!effectiveHidePoweredBy && !isImmersiveChat && (
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
    </div>

      {/* Shell overlays live outside the sidebar/main grid so they never
          become implicit grid children or remount mid-stacking-context. */}
      <CommandPalette onCreateFromGoal={() => setGoalWizardOpen(true)} />
      <GoalWorkflowWizard
        open={goalWizardOpen}
        onOpenChange={setGoalWizardOpen}
        onBuildWorkflow={() => {
          router.push("/workflows/new/builder")
        }}
      />
      <UpgradeModal
        open={upgradeModalOpen}
        onOpenChange={setUpgradeModalOpen}
        subscriptionStatus={planRequired?.subscription_status ?? billingStatusData?.billingState}
      />
      <MesonToolbarPopup />
    </div>
    </MesonToolbarProvider>
  )
}
