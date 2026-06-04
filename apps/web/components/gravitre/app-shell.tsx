"use client"

import { useState, useEffect, startTransition } from "react"
import useSWR, { mutate } from "swr"
import Link from "next/link"
import { Sidebar } from "./sidebar"
import { TopBar } from "./top-bar"
import { NotificationProvider } from "./notification-center"
import { CommandPalette } from "./command-palette"
import { GoalWorkflowWizard } from "./goal-workflow-wizard"
import { useRouter } from "next/navigation"
import { useAuth } from "@/lib/auth-context"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { onboardingApi } from "@/lib/api"
import { Loader2, X } from "lucide-react"
import { Button } from "@/components/ui/button"

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
  const router = useRouter()
  const { user, loading } = useAuth()

  // Fetch billing status
  const { data: billingStatusData, isLoading: billingLoading, error: billingError } = useSWR<BillingStatus>(
    user ? "/api/billing/status" : null, 
    apiFetcher, 
    {
      revalidateOnFocus: false,
      refreshInterval: 30000,
    }
  )

  // Fetch auth/me for onboarding status
  const { data: meData } = useSWR<MeData>(
    user ? "/api/auth/me" : null,
    apiFetcher,
    { revalidateOnFocus: false }
  )

  const canAccessApp = billingStatusData?.canAccessApp ?? false
  const billingStatus = String(billingStatusData?.billingStatus ?? "inactive").toLowerCase()
  const trialEndsAt = billingStatusData?.trialEndsAt
  const requiresUpgrade = billingStatusData?.requiresUpgrade ?? false

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

  // Clear auth transition flags once the protected shell has loaded.
  useEffect(() => {
    if (user && !loading) {
      window.sessionStorage.removeItem("gravitre_auth_redirecting")
      window.sessionStorage.removeItem("gravitre_auth_login_redirect")
    }
  }, [user, loading])

  // Show loading while checking auth and billing
  if (loading || (user && billingLoading && billingStatusData === undefined)) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  // Redirect to login if not authenticated
  if (!user) {
    if (typeof window !== "undefined") {
      router.replace("/login")
    }
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  // Billing gate: redirect users who cannot access the app
  // Note: If billing API fails, fail open for trialing users (allow access)
  if (!billingLoading && !canAccessApp && !billingError) {
    if (typeof window !== "undefined") {
      router.replace("/settings/billing?reason=subscription_required")
    }
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
    <NotificationProvider>
      <div className="flex h-screen overflow-hidden bg-background">
        <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <div className="flex flex-1 flex-col overflow-hidden">
          <TopBar title={title} onMenuClick={() => setSidebarOpen(true)} />
          
          {/* Trial Banner */}
          {billingStatus === "trialing" && !trialBannerDismissed && (
            <div className="border-b border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-900 flex items-center justify-between">
              <span>
                You&apos;re on a 7-day free trial of Node.
                {trialEndsAt && ` ${daysLeft(trialEndsAt)} days left.`}
                {" "}
                <Link href="/pricing" className="underline font-medium hover:text-emerald-700">
                  View plans
                </Link>
              </span>
              <button 
                onClick={handleDismissTrialBanner} 
                aria-label="Dismiss trial banner"
                className="p-1 hover:bg-emerald-100 rounded transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          )}

          {/* Upgrade Nudge for past_due users */}
          {requiresUpgrade && canAccessApp && billingStatus === "past_due" && (
            <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900 flex items-center justify-between">
              <span>
                Your payment needs attention.{" "}
                <Link href="/settings/billing" className="underline font-medium hover:text-amber-700">
                  Update billing
                </Link>
                {" "}to avoid interruption.
              </span>
            </div>
          )}

          {/* Welcome Banner (after bootstrap) */}
          {meData?.onboarding?.seeded && !welcomeDismissed && (
            <div className="border-b border-emerald-300 bg-emerald-100 px-4 py-3 text-sm text-emerald-950">
              <div className="flex items-start justify-between gap-4 max-w-4xl mx-auto">
                <div>
                  <p className="font-medium">Welcome to Gravitre!</p>
                  <p className="text-emerald-800">
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
                    className="p-1 hover:bg-emerald-200 rounded transition-colors"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          )}

          <main className="flex-1 overflow-y-auto">{children}</main>
        </div>
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
    </NotificationProvider>
  )
}
