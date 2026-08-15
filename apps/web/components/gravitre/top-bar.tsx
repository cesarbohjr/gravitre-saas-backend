"use client"

import { useEffect, useMemo, useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { Button } from "@/components/ui/button"
import { GlobalCommandBar } from "./global-command-bar"
import { NotificationCenter } from "./notification-center"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { ThemeToggle } from "@/components/theme-toggle"
import { MesonToolbarTrigger } from "@/components/gravitre/meson-toolbar-popup"
import { cn } from "@/lib/utils"
import { TOUCH_ICON_BUTTON } from "@/lib/design-system"
import { Icon } from "@/lib/icons"
import { UserAccountAvatar } from "@/components/gravitre/user-account-avatar"
import { OrgMonogram } from "@/components/gravitre/organization-logo"
import { useViewMode } from "@/lib/view-mode-context"
import { useAuth } from "@/lib/auth-context"
import {
  getSelectedEnvironmentFromStorage,
  setSelectedEnvironmentInStorage,
  type AppEnvironment,
} from "@/lib/environment-context"
import {
  DEFAULT_DEMO_ORG_ID,
  SECONDARY_DEMO_ORG_ID,
  ensureSelectedOrg,
  getSelectedOrgFromStorage,
  invalidateOrgCache,
  setSelectedOrgInStorage,
} from "@/lib/org-context"
import { formatChargedPlanPriceLabel, getPlan } from "@/lib/plans"

interface TopBarProps {
  title?: string
  onMenuClick?: () => void
  /** Slim bar for chat, assignments, and other work surfaces. */
  compact?: boolean
}

export function TopBar({ title, onMenuClick, compact = false }: TopBarProps) {
  const router = useRouter()
  const pathname = usePathname()
  const [environment, setEnvironment] = useState<AppEnvironment>(() => getSelectedEnvironmentFromStorage())
  const [org, setOrg] = useState(() => getSelectedOrgFromStorage()?.name ?? "Acme Corp")
  const { mode, setMode, isLite } = useViewMode()
  const { user, signOut } = useAuth()

  const switchMode = (next: "admin" | "lite") => {
    setMode(next)
    if (next === "lite" && !pathname.startsWith("/lite")) {
      router.push("/lite")
      return
    }
    if (next === "admin" && pathname.startsWith("/lite")) {
      router.push("/home")
    }
  }

  // Live profile stats (real data, no mocks). Falls back to "—" while loading/unavailable.
  const { data: overviewData } = useSWR<{ activeWorkflows?: number; successRate?: number }>(
    user ? "/api/metrics/overview" : null,
    apiFetcher,
    { revalidateOnFocus: false, refreshInterval: 60_000 },
  )
  const { data: approvalsData } = useSWR<{ approvals?: unknown[] } | unknown[]>(
    user ? "/api/approvals" : null,
    apiFetcher,
    { revalidateOnFocus: false, refreshInterval: 60_000 },
  )
  const { data: billingStatus } = useSWR<{
    planCode?: string | null
    billingStatus?: string
    billingKnown?: boolean
    planUnitAmountCents?: number | null
    planBillingInterval?: string | null
    _auth_degraded?: boolean
  }>(user ? "/api/billing/status" : null, apiFetcher, {
    revalidateOnFocus: false,
    refreshInterval: 120_000,
  })

  const planCodeKnown = Boolean(
    billingStatus?.planCode && billingStatus.billingKnown !== false && !billingStatus._auth_degraded,
  )
  const currentPlan = planCodeKnown ? getPlan(billingStatus?.planCode) : null
  const planPriceLabel = !currentPlan
    ? "—"
    : currentPlan.price === null
      ? "Custom"
      : currentPlan.price === 0
        ? "Free"
        : `${formatChargedPlanPriceLabel(
            currentPlan,
            billingStatus?.planUnitAmountCents,
            billingStatus?.planBillingInterval,
          )}/mo`

  const activeWorkflows =
    typeof overviewData?.activeWorkflows === "number" ? overviewData.activeWorkflows : null
  const successRate =
    typeof overviewData?.successRate === "number" ? overviewData.successRate : null
  const pendingApprovals = Array.isArray((approvalsData as { approvals?: unknown[] })?.approvals)
    ? (approvalsData as { approvals: unknown[] }).approvals.length
    : Array.isArray(approvalsData)
      ? approvalsData.length
      : null

  // Derive user info from auth context
  const userEmail = user?.email ?? "john@acmecorp.com"
  const userName = 
    (user?.user_metadata?.full_name as string | undefined) ||
    (user?.user_metadata?.name as string | undefined) ||
    userEmail.split("@")[0]

  useEffect(() => {
    void ensureSelectedOrg().then((orgId) => {
      const stored = getSelectedOrgFromStorage()
      if (stored?.name) setOrg(stored.name)
      else if (orgId) setOrg("Organization")
    })
    setEnvironment(getSelectedEnvironmentFromStorage())
    const onEnvChange = (event: Event) => {
      const detail = (event as CustomEvent<AppEnvironment>).detail
      if (detail) setEnvironment(detail)
    }
    window.addEventListener("gravitre:environment-changed", onEnvChange)
    return () => window.removeEventListener("gravitre:environment-changed", onEnvChange)
  }, [])

  const selectEnvironment = (next: AppEnvironment) => {
    setEnvironment(next)
    setSelectedEnvironmentInStorage(next)
  }

  const handleOrgChange = (nextOrgId: string, nextOrgName: string) => {
    setOrg(nextOrgName)
    setSelectedOrgInStorage({ id: nextOrgId, name: nextOrgName })
    invalidateOrgCache()
    window.location.reload()
  }

  const userInitials = useMemo(() => {
    const clean = userName.trim()
    if (!clean) return "U"
    const parts = clean.split(/\s+/).filter(Boolean)
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
  }, [userName])

  const handleSignOut = () => {
    signOut()
  }

  return (
    <TooltipProvider delayDuration={300}>
      <header
        data-testid="app-top-bar"
        className={cn(
          // Phones get a taller bar with larger tap targets — the 48px bar with
          // 32px icon buttons tested below the 44px minimum on touch.
          "flex items-center justify-between border-b border-border bg-background px-3 sm:px-4",
          compact ? "h-12 sm:h-10" : "h-16 sm:h-14",
        )}
      >
        {/* Left side - Menu + Org + Environment + Page title */}
        <div className="flex min-w-0 items-center gap-2 sm:gap-3">
          {/* Nav toggle — mobile drawer; tablet+ expands icon rail to labels */}
          <Button
            variant="ghost"
            size="icon"
            className={TOUCH_ICON_BUTTON}
            onClick={onMenuClick}
          >
            <Icon name="menu" size="lg" />
            <span className="sr-only">Toggle navigation</span>
          </Button>

          {!compact ? (
            <>
          {/* Org Selector */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="h-11 gap-2 px-2.5 text-sm font-medium hover:bg-accent sm:h-8 sm:px-2 sm:text-xs"
                aria-label={`Organization: ${org}. Switch organization`}
              >
                <Icon name="company" size="md" className="text-muted-foreground sm:hidden" />
                <Icon name="company" size="sm" className="hidden text-muted-foreground sm:block" />
                <span className="hidden sm:inline">{org}</span>
                <Icon name="caretDown" size="sm" className="text-muted-foreground sm:hidden" />
                <Icon
                  name="caretDown"
                  size="xs"
                  className="hidden text-muted-foreground sm:block"
                />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-52">
              <DropdownMenuItem
                onClick={() => handleOrgChange(DEFAULT_DEMO_ORG_ID, "Acme Corp")}
                className="gap-2.5"
              >
                <OrgMonogram name="Acme Corp" size="sm" />
                Acme Corp
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => handleOrgChange(SECONDARY_DEMO_ORG_ID, "Gravitre Labs")}
                className="gap-2.5"
              >
                <OrgMonogram name="Gravitre Labs" size="sm" />
                Gravitre Labs
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem className="gap-2 text-muted-foreground cursor-pointer" asChild>
                <Link href="/settings/organizations">
                  <Icon name="settings" size="sm" />
                  Manage organizations
                </Link>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <span className="text-muted-foreground/40 hidden sm:inline">/</span>

          {/* Environment Selector */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 gap-2 px-2 text-xs hidden sm:flex hover:bg-accent"
              >
                <Icon 
                  name={environment === "production" ? "production" : "staging"} 
                  size="sm"
                  className={environment === "production" ? "text-success" : "text-warning"}
                />
                <span className="capitalize">{environment}</span>
                <Icon name="caretDown" size="xs" className="text-muted-foreground" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-40">
              <DropdownMenuItem onClick={() => selectEnvironment("production")} className="gap-2">
                <Icon name="production" size="sm" className="text-success" />
                Production
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => selectEnvironment("staging")} className="gap-2">
                <Icon name="staging" size="sm" className="text-warning" />
                Staging
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {title && !compact ? (
            <>
              <span className="text-muted-foreground/40 hidden md:inline">/</span>
              {/* On phones the org chip collapses to an icon, so the page title
                  is the only text label — show it there too, at a legible size. */}
              <span
                className="max-w-[9rem] truncate text-base font-semibold text-foreground sm:hidden"
                aria-current="page"
              >
                {title}
              </span>
              <span
                className="hidden max-w-[240px] truncate text-sm font-medium text-foreground md:block"
                aria-current="page"
              >
                {title}
              </span>
            </>
          ) : null}
            </>
          ) : null}
        </div>

        {/* Right side - Controls */}
        <div className="flex items-center gap-1 sm:gap-1.5">
          {/* Global Command Bar */}
          <GlobalCommandBar />

          {/* Admin/Lite Mode Toggle */}
          {!compact ? (
          <div className="hidden sm:flex items-center gap-0.5 p-0.5 rounded-full bg-secondary/50 border border-border/50">
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={() => switchMode("admin")}
                  className={cn(
                    "px-2.5 py-1 rounded-full text-xs font-medium transition-all duration-200",
                    mode === "admin"
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  Admin
                </button>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="text-xs">
                Full access to training, workflows, and system configuration
              </TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={() => switchMode("lite")}
                  className={cn(
                    "px-2.5 py-1 rounded-full text-xs font-medium transition-all duration-200",
                    mode === "lite"
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  Lite
                </button>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="text-xs">
                Simplified view for assigning work and viewing results
              </TooltipContent>
            </Tooltip>
          </div>
          ) : null}

          {/* Theme Toggle */}
          <ThemeToggle />

          {/* B1: Meson build chrome is full-seat only — Lite uses assigned workflows, not the builder. */}
          {!compact && !isLite ? <MesonToolbarTrigger /> : null}

          {/* Notifications */}
          <NotificationCenter />

          {/* User Avatar */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="group relative h-11 w-11 rounded-full p-0 hover:bg-accent sm:h-8 sm:w-8" aria-label="Account menu">
                <UserAccountAvatar
                  useCurrentUser
                  size="md"
                  className="relative ring-1 ring-border transition-colors group-hover:ring-primary/40 sm:h-8 sm:w-8"
                />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-[calc(100vw-2rem)] sm:w-72 max-w-72 p-0 overflow-hidden">
              {/* Profile header with gradient */}
              <div className="relative overflow-hidden border-b border-border bg-muted/40 px-4 py-5">
                <div className="relative flex items-center gap-3">
                  <div className="relative">
                    <UserAccountAvatar useCurrentUser size="xl" />
                    <div className="absolute -bottom-0.5 -right-0.5 h-3.5 w-3.5 rounded-full bg-success ring-2 ring-background" />
                  </div>
                  <div className="flex flex-col">
                    <span className="text-sm font-semibold text-foreground">{userName}</span>
                    <span className="text-xs text-muted-foreground">{userEmail}</span>
                    <span className="text-[10px] text-muted-foreground mt-0.5 flex items-center gap-1">
                      <span className="h-1.5 w-1.5 rounded-full bg-success" />
                      Active now
                    </span>
                  </div>
                </div>
              </div>
              
              {/* Quick stats */}
              <div className="grid grid-cols-3 divide-x divide-border border-b border-border">
                <div className="px-3 py-2.5 text-center">
                  <p className="text-lg font-semibold text-foreground">
                    {activeWorkflows ?? "—"}
                  </p>
                  <p className="text-[10px] text-muted-foreground">Workflows</p>
                </div>
                <div className="px-3 py-2.5 text-center">
                  <p className="text-lg font-semibold text-foreground">
                    {pendingApprovals ?? "—"}
                  </p>
                  <p className="text-[10px] text-muted-foreground">Approvals</p>
                </div>
                <div className="px-3 py-2.5 text-center">
                  <p className="text-lg font-semibold text-foreground">
                    {successRate !== null ? `${Math.round(successRate)}%` : "—"}
                  </p>
                  <p className="text-[10px] text-muted-foreground">Success</p>
                </div>
              </div>
              
              <div className="p-1.5">
                <DropdownMenuItem className="gap-3 cursor-pointer rounded-lg px-3 py-2.5 transition-colors" asChild>
                  <Link href="/settings/profile">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                      <Icon name="user" size="sm" className="text-primary" />
                    </div>
                    <div>
                      <p className="text-sm font-medium">Edit Profile</p>
                      <p className="text-[10px] text-muted-foreground">Manage your personal info</p>
                    </div>
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem className="gap-3 cursor-pointer rounded-lg px-3 py-2.5 transition-colors" asChild>
                  <Link href="/settings">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary">
                      <Icon name="settings" size="sm" className="text-muted-foreground" />
                    </div>
                    <div>
                      <p className="text-sm font-medium">Settings</p>
                      <p className="text-[10px] text-muted-foreground">Account & preferences</p>
                    </div>
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem className="gap-3 cursor-pointer rounded-lg px-3 py-2.5 transition-colors" asChild>
                  <Link href="/settings?section=team">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary">
                      <Icon name="team" size="sm" className="text-muted-foreground" />
                    </div>
                    <div>
                      <p className="text-sm font-medium">Team</p>
                      <p className="text-[10px] text-muted-foreground">8 members</p>
                    </div>
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem className="gap-3 cursor-pointer rounded-lg px-3 py-2.5 transition-colors" asChild>
                  <Link href="/settings/billing">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary">
                      <Icon name="billing" size="sm" className="text-muted-foreground" />
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium">Billing</p>
                      <p className="text-[10px] text-muted-foreground">
                        {currentPlan ? `${currentPlan.name} Plan` : "Plan status"}
                      </p>
                    </div>
                    <span className="text-xs font-medium text-primary">{planPriceLabel}</span>
                  </Link>
                </DropdownMenuItem>
              </div>
              
              <DropdownMenuSeparator className="my-0" />
              
              <div className="p-1.5">
                <DropdownMenuItem className="gap-3 cursor-pointer rounded-lg px-3 py-2" asChild>
                  <Link href="/docs">
                    <Icon name="help" size="sm" className="text-muted-foreground" />
                    <span className="text-sm">Help & Documentation</span>
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem
                  className="gap-3 cursor-pointer rounded-lg px-3 py-2 text-destructive focus:text-destructive focus:bg-destructive/10"
                  onClick={handleSignOut}
                >
                  <Icon name="signOut" size="sm" />
                  <span className="text-sm">Sign out</span>
                </DropdownMenuItem>
              </div>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>
    </TooltipProvider>
  )
}
