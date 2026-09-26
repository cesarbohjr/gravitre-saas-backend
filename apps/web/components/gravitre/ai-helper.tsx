"use client"

/**
 * GravitreAIHelper — Phase 2–5 of the "Gravitre AI Agent Workspace" redesign.
 *
 * Phase 5: opens Float in place (no `router.push("/ai")`). The root-mounted
 * AiWorkspace host owns the live useChat instance across routes.
 */

import { useCallback } from "react"
import useSWR from "swr"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { ADMIN_SIDEBAR_NAV, isSidebarItemActive } from "@/components/gravitre/sidebar-nav-config"
import { NucleoChat } from "@/components/icons/nucleo/semantic"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { GravitreOrb } from "@/components/gravitre/assistant/voice-presentation"
import { cn } from "@/lib/utils"
import { formatGravitreAiContextLabel, gravitreHelperStatusCopy } from "@/lib/gravitre-ai-context-label"
import { GRAVITRE_AI_FLOAT_ENABLED } from "@/lib/ai-workspace-flags"
import { useGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"
import { useAuth } from "@/lib/auth-context"
import {
  deriveGravitreHelperPresence,
  GRAVITRE_HELPER_PRESENCE_COPY,
  GRAVITRE_HELPER_PRESENCE_DOT,
  type GravitreHelperPresence,
} from "@/lib/gravitre-ai-presence"

/**
 * Whether the Helper should ever render on the given pathname. Mirrors
 * `shouldShowMesonToolbar`'s `/ai` check exactly (same reasoning: `/ai`
 * already is the full chat surface).
 */
/** The builder's bottom toolbar and Meson panel leave no room for the labelled pill below xl. */
export function isWorkflowBuilderPath(pathname: string): boolean {
  return /^\/workflows\/[^/]+\/builder(\/|$)/.test(pathname.split("?")[0] ?? "")
}

export function shouldShowGravitreAIHelper(pathname: string): boolean {
  const path = pathname.split("?")[0] ?? ""
  return path !== "/ai" && !path.startsWith("/ai/")
}

/**
 * Whether the launcher may render at all.
 *
 * Until now the only thing keeping the authenticated assistant off the marketing
 * site was the `x-gravitre-marketing` request header picking `MarketingProviders`
 * instead of `AppProviders`. That is a routing detail, not authentication: any path
 * where the header is missing at SSR -- a cache layer, a route added outside the
 * (marketing) group, a CDN quirk -- renders the authenticated assistant to an
 * anonymous visitor, because nothing here ever asked who they were.
 *
 * `loading` is treated as NOT allowed on purpose. Defaulting to visible while the
 * session resolves is what produces a flash of authenticated UI for logged-out
 * visitors, and it is also the failure mode that survives a logout: better to
 * appear a moment late than to appear to the wrong person.
 */
export function mayShowGravitreAIHelper(args: {
  pathname: string
  hasSession: boolean
  loading: boolean
  floatEnabled: boolean
  floatOpen: boolean
}): boolean {
  if (!args.floatEnabled) return false
  if (args.loading) return false
  if (!args.hasSession) return false
  if (args.floatOpen) return false
  return shouldShowGravitreAIHelper(args.pathname)
}

/** The navigation destination the user is on, so the dock says what it will act on. */
export function routeContextLabel(pathname: string): string | null {
  const path = pathname.split("?")[0] ?? ""
  for (const group of ADMIN_SIDEBAR_NAV) {
    for (const item of group.items) {
      if (item.liteWork || item.name === "Getting Started") continue
      if (isSidebarItemActive(path, item.href)) return item.name
    }
  }
  if (path.startsWith("/marketplace")) return "Marketplace"
  return null
}

function helperOrbSpeaker(presence: GravitreHelperPresence): "user" | "agent" {
  if (presence === "listening") return "user"
  return "agent"
}

export function GravitreAIHelper() {
  const {
    pageContext,
    floatWorkspaceOpen,
    restoreFromHelper,
    takeHelperFocusRequest,
    conversation,
    approval,
    voice,
    agentScope,
  } = useGravitreAIWorkspace()
  const { user, loading } = useAuth()
  const { data: approvalsData } = useSWR<{ approvals?: Array<{ status?: string }> }>(
    user?.id ? "/api/approvals" : null,
    apiFetcher,
    { revalidateOnFocus: false, dedupingInterval: 30_000 },
  )
  const pendingApprovals =
    approvalsData?.approvals?.filter((entry) => entry.status === "pending").length ?? 0
  const routeLabel = routeContextLabel(pageContext.pathname)
  const focusOnMount = useCallback(
    (node: HTMLButtonElement | null) => {
      if (node && takeHelperFocusRequest()) node.focus()
    },
    [takeHelperFocusRequest],
  )

  if (
    !mayShowGravitreAIHelper({
      pathname: pageContext.pathname,
      hasSession: Boolean(user?.id),
      loading,
      floatEnabled: GRAVITRE_AI_FLOAT_ENABLED,
      floatOpen: floatWorkspaceOpen,
    })
  ) {
    return null
  }

  const presence = deriveGravitreHelperPresence({ conversation, approval, voice })
  const copy = GRAVITRE_HELPER_PRESENCE_COPY[presence]
  const contextLabel = formatGravitreAiContextLabel({
    agentName: agentScope?.name,
    selectedKind: pageContext.selected?.kind,
    selectedLabel: pageContext.selected?.label,
  })
  const helperStatus = gravitreHelperStatusCopy(presence, copy.label, contextLabel)
  const orbActive =
    presence === "listening" ||
    presence === "thinking" ||
    presence === "executing"

  // Reopens at whatever mode the user left, rather than always forcing "float".
  // Someone who minimised from fullscreen used to come back to a small window.
  const handleOpen = restoreFromHelper

  // "Open AI Chat" is the required accessible name. The presence label stays on the
  // end so a screen reader also hears whether voice is live — the status dot conveys
  // that visually only.
  const accessibleName = `Open AI Chat — ${copy.label}`
  const onBuilder = isWorkflowBuilderPath(pageContext.pathname)

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          ref={focusOnMount}
          type="button"
          onClick={handleOpen}
          data-gravitre-ai-helper=""
          data-gravitre-ai-dock={onBuilder ? "canvas" : "workspace"}
          className={cn(
            "fixed left-5 z-40 flex items-center gap-2.5 rounded-full border border-[color:var(--g-border-default)]",
            "max-md:bottom-[calc(56px+env(safe-area-inset-bottom)+12px)] md:bottom-5",
            onBuilder
              ? "md:left-[calc(var(--np-sidebar-rail)+12px)] md:[:root:has([data-nav-expanded=true])_&]:left-[calc(var(--np-sidebar)+12px)]"
              : cn(
                  // Operating layer: a context dock centred on the workspace panel,
                  // not a support bubble parked in a corner.
                  "md:left-[calc(50%+var(--np-sidebar-rail)/2)] md:[:root:has([data-nav-expanded=true])_&]:left-[calc(50%+var(--np-sidebar)/2)]",
                  "md:-translate-x-1/2 md:w-[min(460px,calc(100vw-var(--np-sidebar)-64px))] md:rounded-[14px] md:py-1.5 md:pl-1.5 md:pr-2",
                ),
            "bg-[color:var(--g-surface-1)] px-3 py-2 shadow-[0_10px_32px_-14px_rgb(16_24_40/0.35),0_0_0_1px_var(--g-border-subtle)] backdrop-blur transition-colors",
            "hover:border-[color:var(--g-brand-border)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--g-brand)]/40",
          )}
          aria-label={accessibleName}
          aria-expanded={false}
        >
          <span className="relative flex h-9 w-9 shrink-0 items-center justify-center">
            {orbActive ? (
              <GravitreOrb
                speaker={helperOrbSpeaker(presence)}
                className="!h-9 !w-9"
                amplitude={presence === "listening" ? 0.55 : 0.35}
              />
            ) : (
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-[color:var(--g-brand)] to-emerald-700 text-white md:rounded-[10px]">
                {/* A conversation bubble, not the abstract agent glyph: the control
                    has to read as "AI Chat" at a glance. */}
                <NucleoChat className="h-4 w-4" />
              </span>
            )}
            <span
              className={cn(
                "absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full border-2 border-[color:var(--g-surface-1)]",
                GRAVITRE_HELPER_PRESENCE_DOT[presence],
                (presence === "thinking" || presence === "executing") && "animate-pulse",
              )}
              aria-hidden
            />
          </span>
          <span
            data-gravitre-ai-helper-label=""
            className={cn(
              "hidden min-w-0 flex-col items-start pr-1",
              onBuilder ? "xl:flex" : "sm:flex md:flex-1",
            )}
          >
            <span className="text-xs font-semibold text-[color:var(--g-text-primary)] md:text-[13px]">
              {onBuilder ? "Gravitre AI" : "Ask Gravitre"}
            </span>
            <span className={cn("max-w-[180px] truncate text-[11px] font-medium md:max-w-[240px]", copy.tone)}>
              {helperStatus}
            </span>
          </span>
          {onBuilder ? null : (
            <span className="hidden shrink-0 items-center gap-1.5 md:flex" aria-hidden>
              {pendingApprovals > 0 ? (
                <span className="rounded-md bg-[color:var(--g-signal-soft)] px-1.5 py-0.5 text-[11px] font-medium text-[color:var(--g-signal)]">
                  {pendingApprovals} to approve
                </span>
              ) : null}
              {routeLabel ? (
                <span className="rounded-md border border-[color:var(--g-border-default)] px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground">
                  {routeLabel}
                </span>
              ) : null}
            </span>
          )}
        </button>
      </TooltipTrigger>
      <TooltipContent side="top">AI Chat</TooltipContent>
    </Tooltip>
  )
}
