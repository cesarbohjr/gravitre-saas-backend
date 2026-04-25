"use client"

import { useEffect, useMemo, useState } from "react"
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
import { cn } from "@/lib/utils"
import { Icon } from "@/lib/icons"
import { useViewMode } from "@/lib/view-mode-context"
import { supabaseClient } from "@/lib/supabaseClient"

interface TopBarProps {
  title?: string
  onMenuClick?: () => void
}

export function TopBar({ title, onMenuClick }: TopBarProps) {
  const [environment, setEnvironment] = useState<"production" | "staging">("production")
  const [org, setOrg] = useState("Acme Corp")
  const [userEmail, setUserEmail] = useState("john@acmecorp.com")
  const [userName, setUserName] = useState("John Doe")
  const { mode, setMode, isLite } = useViewMode()

  useEffect(() => {
    let mounted = true
    supabaseClient.auth.getUser().then(({ data }) => {
      if (!mounted || !data.user) return
      const email = data.user.email ?? "unknown@user"
      const displayName =
        (data.user.user_metadata?.full_name as string | undefined) ||
        (data.user.user_metadata?.name as string | undefined) ||
        email.split("@")[0]

      setUserEmail(email)
      setUserName(displayName)
    })

    const {
      data: { subscription },
    } = supabaseClient.auth.onAuthStateChange((_event, session) => {
      if (!mounted) return
      const email = session?.user?.email ?? "john@acmecorp.com"
      const displayName =
        (session?.user?.user_metadata?.full_name as string | undefined) ||
        (session?.user?.user_metadata?.name as string | undefined) ||
        email.split("@")[0]

      setUserEmail(email)
      setUserName(displayName)
    })

    return () => {
      mounted = false
      subscription.unsubscribe()
    }
  }, [])

  const userInitials = useMemo(() => {
    const clean = userName.trim()
    if (!clean) return "U"
    const parts = clean.split(/\s+/).filter(Boolean)
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
  }, [userName])

  const handleSignOut = async () => {
    await supabaseClient.auth.signOut()
    window.location.assign("/login")
  }

  return (
    <TooltipProvider delayDuration={300}>
      <header className="flex h-12 sm:h-14 items-center justify-between border-b border-border bg-background px-3 sm:px-4">
        {/* Left side - Menu + Org + Environment + Page title */}
        <div className="flex items-center gap-3">
          {/* Mobile Menu Button - Only show on mobile, sidebar visible on tablet+ */}
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 md:hidden"
            onClick={onMenuClick}
          >
            <Icon name="rows" size="lg" />
            <span className="sr-only">Toggle menu</span>
          </Button>

          {/* Org Selector */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 gap-2 px-2 text-xs font-medium hover:bg-accent"
              >
                <div className="flex h-5 w-5 items-center justify-center rounded bg-foreground">
                  <Icon name="company" size="xs" className="text-background" />
                </div>
                <span className="hidden sm:inline">{org}</span>
                <Icon name="caretDown" size="xs" className="text-muted-foreground" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-48">
              <DropdownMenuItem onClick={() => setOrg("Acme Corp")} className="gap-2">
                <div className="flex h-5 w-5 items-center justify-center rounded bg-foreground">
                  <Icon name="company" size="xs" className="text-background" />
                </div>
                Acme Corp
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setOrg("Initech")} className="gap-2">
                <div className="flex h-5 w-5 items-center justify-center rounded bg-foreground">
                  <Icon name="company" size="xs" className="text-background" />
                </div>
                Initech
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem className="gap-2 text-muted-foreground cursor-pointer" asChild>
                <a href="/settings/organizations">
                  <Icon name="settings" size="sm" />
                  Manage organizations
                </a>
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
              <DropdownMenuItem onClick={() => setEnvironment("production")} className="gap-2">
                <Icon name="production" size="sm" className="text-success" />
                Production
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setEnvironment("staging")} className="gap-2">
                <Icon name="staging" size="sm" className="text-warning" />
                Staging
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {title && (
            <>
              <span className="text-muted-foreground/40 hidden md:inline">/</span>
              <h1 className="text-sm font-medium text-foreground hidden md:block">{title}</h1>
            </>
          )}
        </div>

        {/* Right side - Controls */}
        <div className="flex items-center gap-1 sm:gap-1.5">
          {/* Global Command Bar */}
          <GlobalCommandBar />

          {/* Admin/Lite Mode Toggle */}
          <div className="hidden sm:flex items-center gap-0.5 p-0.5 rounded-lg bg-secondary/50 border border-border/50">
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={() => setMode("admin")}
                  className={cn(
                    "px-2.5 py-1 rounded-md text-xs font-medium transition-all duration-200",
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
                  onClick={() => setMode("lite")}
                  className={cn(
                    "px-2.5 py-1 rounded-md text-xs font-medium transition-all duration-200",
                    mode === "lite"
                      ? "bg-emerald-500/10 text-emerald-500 shadow-sm border border-emerald-500/20"
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

          {/* Theme Toggle */}
          <ThemeToggle />

          {/* Notifications */}
          <NotificationCenter />

          {/* User Avatar */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8 rounded-full hover:bg-accent group relative">
                <div className="absolute -inset-0.5 bg-gradient-to-r from-blue-500 to-purple-500 rounded-full opacity-0 group-hover:opacity-50 blur transition-opacity duration-300" />
                <div className="relative flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-slate-700 to-slate-900 text-xs font-medium text-white ring-2 ring-background">
                  {userInitials}
                </div>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-[calc(100vw-2rem)] sm:w-72 max-w-72 p-0 overflow-hidden">
              {/* Profile header with gradient */}
              <div className="relative px-4 py-5 border-b border-border overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-br from-blue-500/10 via-purple-500/5 to-transparent" />
                <div className="absolute top-0 right-0 w-24 h-24 bg-purple-500/10 rounded-full blur-2xl -translate-y-1/2 translate-x-1/2" />
                <div className="relative flex items-center gap-3">
                  <div className="relative">
                    <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-slate-700 to-slate-900 text-base font-semibold text-white">
                      {userInitials}
                    </div>
                    <div className="absolute -bottom-0.5 -right-0.5 h-3.5 w-3.5 rounded-full bg-emerald-500 ring-2 ring-background" />
                  </div>
                  <div className="flex flex-col">
                    <span className="text-sm font-semibold text-foreground">{userName}</span>
                    <span className="text-xs text-muted-foreground">{userEmail}</span>
                    <span className="text-[10px] text-muted-foreground mt-0.5 flex items-center gap-1">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                      Active now
                    </span>
                  </div>
                </div>
              </div>
              
              {/* Quick stats */}
              <div className="grid grid-cols-3 divide-x divide-border border-b border-border">
                <div className="px-3 py-2.5 text-center">
                  <p className="text-lg font-semibold text-foreground">47</p>
                  <p className="text-[10px] text-muted-foreground">Workflows</p>
                </div>
                <div className="px-3 py-2.5 text-center">
                  <p className="text-lg font-semibold text-foreground">156</p>
                  <p className="text-[10px] text-muted-foreground">Approvals</p>
                </div>
                <div className="px-3 py-2.5 text-center">
                  <p className="text-lg font-semibold text-foreground">98%</p>
                  <p className="text-[10px] text-muted-foreground">Success</p>
                </div>
              </div>
              
              <div className="p-1.5">
                <DropdownMenuItem className="gap-3 cursor-pointer rounded-lg px-3 py-2.5 transition-colors" asChild>
                  <a href="/settings/profile">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500/10">
                      <Icon name="user" size="sm" className="text-blue-500" />
                    </div>
                    <div>
                      <p className="text-sm font-medium">Edit Profile</p>
                      <p className="text-[10px] text-muted-foreground">Manage your personal info</p>
                    </div>
                  </a>
                </DropdownMenuItem>
                <DropdownMenuItem className="gap-3 cursor-pointer rounded-lg px-3 py-2.5 transition-colors" asChild>
                  <a href="/settings">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary">
                      <Icon name="settings" size="sm" className="text-muted-foreground" />
                    </div>
                    <div>
                      <p className="text-sm font-medium">Settings</p>
                      <p className="text-[10px] text-muted-foreground">Account & preferences</p>
                    </div>
                  </a>
                </DropdownMenuItem>
                <DropdownMenuItem className="gap-3 cursor-pointer rounded-lg px-3 py-2.5 transition-colors" asChild>
                  <a href="/settings?section=team">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary">
                      <Icon name="team" size="sm" className="text-muted-foreground" />
                    </div>
                    <div>
                      <p className="text-sm font-medium">Team</p>
                      <p className="text-[10px] text-muted-foreground">8 members</p>
                    </div>
                  </a>
                </DropdownMenuItem>
                <DropdownMenuItem className="gap-3 cursor-pointer rounded-lg px-3 py-2.5 transition-colors" asChild>
                  <a href="/settings/billing">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10">
                      <Icon name="billing" size="sm" className="text-emerald-500" />
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium">Billing</p>
                      <p className="text-[10px] text-muted-foreground">Business Plan</p>
                    </div>
                    <span className="text-xs font-medium text-emerald-500">$499/mo</span>
                  </a>
                </DropdownMenuItem>
              </div>
              
              <DropdownMenuSeparator className="my-0" />
              
              <div className="p-1.5">
                <DropdownMenuItem className="gap-3 cursor-pointer rounded-lg px-3 py-2" asChild>
                  <a href="/docs">
                    <Icon name="help" size="sm" className="text-muted-foreground" />
                    <span className="text-sm">Help & Documentation</span>
                  </a>
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
