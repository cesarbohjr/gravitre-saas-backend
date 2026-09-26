"use client"

import { useEffect, useMemo, useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { organizationsApi } from "@/lib/api"
import type { Organization } from "@/types/api"
import { toast } from "sonner"
import { useTheme } from "next-themes"
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
  ensureSelectedOrg,
  getSelectedOrgFromStorage,
  invalidateOrgCache,
  setSelectedOrgInStorage,
} from "@/lib/org-context"
import { formatPlanPrice, getPlan } from "@/lib/plans"

interface TopBarProps {
  title?: string
  onMenuClick?: () => void
  /** Slim bar for chat, assignments, and other work surfaces. */
  compact?: boolean
}

const TOPBAR_MINIMIZED_KEY = "gravitre-topbar-minimized"

export function TopBar({ title, onMenuClick, compact = false }: TopBarProps) {
  const router = useRouter()
  const pathname = usePathname()
  const [environment, setEnvironment] = useState<AppEnvironment>(() => getSelectedEnvironmentFromStorage())
  const [org, setOrg] = useState(() => getSelectedOrgFromStorage()?.name ?? "Organization")
  const [orgId, setOrgId] = useState(() => getSelectedOrgFromStorage()?.id ?? null)
  const [isSwitchingOrg, setIsSwitchingOrg] = useState(false)
  const [minimized, setMinimized] = useState(false)
  const { mode, setMode, isLite } = useViewMode()
  const { user, signOut } = useAuth()
  const { resolvedTheme, setTheme } = useTheme()

  useEffect(() => {
    try {
      setMinimized(localStorage.getItem(TOPBAR_MINIMIZED_KEY) === "true")
    } catch {
      /* ignore */
    }
  }, [])

  function toggleMinimized() {
    setMinimized((prev) => {
      const next = !prev
      try {
        localStorage.setItem(TOPBAR_MINIMIZED_KEY, String(next))
      } catch {
        /* ignore */
      }
      return next
    })
  }

  const chromeQuiet = compact || minimized

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
    _auth_degraded?: boolean
  }>(user ? "/api/billing/status" : null, apiFetcher, {
    revalidateOnFocus: false,
    refreshInterval: 120_000,
  })

  // Real org-switcher membership list — the same organizationsApi.list() call
  // that already correctly powers /settings/organizations and the current-org
  // label below. Previously this dropdown rendered two hardcoded demo orgs
  // ("Acme Corp" / "Gravitre Labs") that were never wired to any API, so any
  // real user who clicked one would switch their session's x-org-id to a
  // legacy demo org they aren't a member of and get 403s app-wide.
  const { data: orgsData } = useSWR(
    user ? "organizations:list" : null,
    () => organizationsApi.list(),
    { revalidateOnFocus: false },
  )
  const memberOrgs = (orgsData?.organizations as Organization[] | undefined) ?? []

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
        : `${formatPlanPrice(currentPlan)}/mo`

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
  const userEmail = user?.email ?? ""
  const userName = 
    (user?.user_metadata?.full_name as string | undefined) ||
    (user?.user_metadata?.name as string | undefined) ||
    userEmail.split("@")[0]

  useEffect(() => {
    void ensureSelectedOrg().then((resolvedOrgId) => {
      const stored = getSelectedOrgFromStorage()
      if (stored?.name) setOrg(stored.name)
      else if (resolvedOrgId) setOrg("Organization")
      setOrgId(stored?.id ?? resolvedOrgId ?? null)
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

  const handleOrgChange = async (nextOrgId: string, nextOrgName: string) => {
    if (nextOrgId === orgId || isSwitchingOrg) return
    setIsSwitchingOrg(true)
    try {
      // Real backend switch (STA-72 multi-org) — same call already proven at
      // /settings/organizations. Persisting to localStorage afterwards keeps
      // every org-scoped fetch's `x-org-id` header (lib/fetcher.ts) in sync.
      await organizationsApi.switch(nextOrgId)
      setOrg(nextOrgName)
      setSelectedOrgInStorage({ id: nextOrgId, name: nextOrgName })
      invalidateOrgCache()
      window.location.reload()
    } catch (error) {
      console.error("Failed to switch organization", error)
      toast.error(error instanceof Error ? error.message : "Failed to switch organization")
      setIsSwitchingOrg(false)
    }
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
          // Graphite command frame: workspace → environment → page left, command centre, account right.
          "dark relative flex items-center justify-between bg-[color:var(--g-frame)] px-3 text-foreground sm:px-4 md:pl-1 md:pr-3",
          chromeQuiet ? "h-10 sm:h-10" : "h-12",
        )}
      >
        {/* Left side - Menu + (mobile) Org + Environment + Page title */}
        <div className="flex min-w-0 flex-1 items-center gap-2 sm:gap-2.5">
          {/* Nav toggle — mobile drawer; tablet+ expands icon rail to labels */}
          <Button
            variant="ghost"
            size="icon"
            className={TOUCH_ICON_BUTTON}
            data-testid="nav-toggle"
            onClick={onMenuClick}
          >
            <Icon name="menu" size="lg" />
            <span className="sr-only">Toggle navigation</span>
          </Button>

          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="hidden h-8 w-8 shrink-0 md:inline-flex"
            onClick={toggleMinimized}
            aria-pressed={minimized}
            aria-label={minimized ? "Expand top menu" : "Minimize top menu"}
            title={minimized ? "Expand top menu" : "Minimize top menu"}
          >
            <Icon name={minimized ? "chevronDown" : "chevronUp"} size="sm" />
          </Button>

          {!chromeQuiet ? (
            <>
          {/* Org Selector */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="h-11 gap-1.5 rounded-[4px] px-2.5 text-sm font-medium hover:bg-accent sm:h-8 sm:px-2 sm:text-[13px]"
                aria-label={`Organization: ${org}. Switch organization`}
                data-testid="workspace-identity"
              >
                <Icon name="company" size="md" className="text-muted-foreground sm:hidden" />
                <span className="hidden max-w-[180px] truncate font-semibold sm:inline">{org}</span>
                <Icon name="caretDown" size="sm" className="text-muted-foreground sm:hidden" />
                <Icon
                  name="caretDown"
                  size="xs"
                  className="hidden text-muted-foreground sm:block"
                />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-52">
              {memberOrgs.length > 0 ? (
                memberOrgs.map((memberOrg) => (
                  <DropdownMenuItem
                    key={memberOrg.id}
                    onClick={() => void handleOrgChange(memberOrg.id, memberOrg.name)}
                    disabled={isSwitchingOrg}
                    className="gap-2.5"
                  >
                    <OrgMonogram name={memberOrg.name} size="sm" />
                    <span className="flex-1 truncate">{memberOrg.name}</span>
                    {memberOrg.id === orgId ? (
                      <Icon name="check" size="sm" className="text-primary" />
                    ) : null}
                  </DropdownMenuItem>
                ))
              ) : (
                <DropdownMenuItem disabled className="gap-2.5 text-muted-foreground">
                  {org}
                </DropdownMenuItem>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem className="gap-2 text-muted-foreground cursor-pointer" asChild>
                <Link href="/settings/organizations">
                  <Icon name="settings" size="sm" />
                  Manage organizations
                </Link>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <span className="hidden text-muted-foreground/50 sm:inline" aria-hidden>/</span>

          {/* Environment — part of the workspace path, not a separate control cluster */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="hidden h-8 gap-1.5 rounded-[4px] px-2 text-xs font-medium text-muted-foreground hover:bg-accent hover:text-foreground sm:flex"
                aria-label={`Environment: ${environment}. Switch environment`}
              >
                <span
                  aria-hidden
                  className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    environment === "production" ? "bg-[color:var(--g-brand)]" : "bg-warning",
                  )}
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

          {title && !chromeQuiet ? (
            <>
              {/* On phones the org chip collapses to an icon, so the page title
                  is the only text label — show it there too, at a legible size. */}
              <span
                className="max-w-[9rem] truncate text-base font-semibold text-foreground sm:hidden"
                aria-current="page"
              >
                {title}
              </span>
              <span className="hidden text-muted-foreground/50 md:inline" aria-hidden>/</span>
              <span
                className="hidden max-w-[280px] truncate pl-1 text-[13px] font-semibold text-foreground md:block"
                aria-current="page"
              >
                {title}
              </span>
            </>
          ) : null}
            </>
          ) : title ? (
            <span
              className="max-w-[12rem] truncate text-sm font-semibold text-foreground"
              aria-current="page"
            >
              {title}
            </span>
          ) : null}
        </div>

        {/* Right side - Controls */}
        <div className="flex items-center gap-1 sm:gap-1.5">
          {/* Global Command Bar — centred command slot on desktop */}
          <div className="lg:absolute lg:left-1/2 lg:top-1/2 lg:-translate-x-1/2 lg:-translate-y-1/2">
            <GlobalCommandBar />
          </div>

          {/* Admin/Lite Mode Toggle */}
          {!chromeQuiet ? (
          <div className="hidden items-center gap-px rounded-[4px] border border-[color:var(--g-frame-rule)] p-0.5 sm:flex">
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={() => switchMode("admin")}
                  className={cn(
                    "rounded-[2px] px-2 py-0.5 text-xs font-medium transition-colors duration-150",
                    mode === "admin"
                      ? "bg-white/[0.12] text-foreground"
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
                    "rounded-[2px] px-2 py-0.5 text-xs font-medium transition-colors duration-150",
                    mode === "lite"
                      ? "bg-white/[0.12] text-foreground"
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

          {/* B1: Meson build chrome is full-seat only — Lite uses assigned workflows, not the builder. */}
          {!chromeQuiet && !isLite ? <MesonToolbarTrigger /> : null}

          {/* Notifications */}
          <NotificationCenter />

          {/* User Avatar */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="group relative h-11 w-11 rounded-full p-0 hover:bg-accent sm:h-8 sm:w-8" aria-label="Account menu" data-testid="account-identity">
                <UserAccountAvatar
                  useCurrentUser
                  size="md"
                  className="relative ring-1 ring-[color:var(--g-frame-rule)] transition-colors group-hover:ring-foreground/40 sm:h-7 sm:w-7"
                />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-[calc(100vw-2rem)] sm:w-72 max-w-72 overflow-hidden border-divide p-0 shadow-aceternity">
              {/* Profile header with gradient */}
              <div className="relative overflow-hidden border-b border-divide bg-[color:var(--g-background)] px-4 py-4">
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
              <div className="grid grid-cols-3 divide-x divide-divide border-b border-divide">
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
                      <p className="text-sm font-medium">Edit profile</p>
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
                      <p className="text-[10px] text-muted-foreground">Members and roles</p>
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

              <div className="flex items-center justify-between gap-3 px-4 py-2.5">
                <span className="text-sm">Appearance</span>
                <div role="radiogroup" aria-label="Appearance" className="inline-flex items-center gap-0.5 rounded-[var(--np-radius-md)] bg-[color:var(--g-background-muted)] p-0.5">
                  {(["light", "dark"] as const).map((option) => (
                    <button
                      key={option}
                      type="button"
                      role="radio"
                      aria-checked={resolvedTheme === option}
                      onClick={() => setTheme(option)}
                      className={cn(
                        "rounded-[6px] px-2.5 py-1 text-xs font-medium capitalize transition-colors",
                        resolvedTheme === option
                          ? "bg-background text-foreground shadow-[0_0_0_1px_var(--g-border-default)]"
                          : "text-muted-foreground hover:text-foreground",
                      )}
                    >
                      {option}
                    </button>
                  ))}
                </div>
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
