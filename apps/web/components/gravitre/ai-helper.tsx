"use client"

/**
 * GravitreAIHelper — Phase 2–5 of the "Gravitre AI Agent Workspace" redesign.
 *
 * Phase 5: opens Float in place (no `router.push("/ai")`). The root-mounted
 * AiWorkspace host owns the live useChat instance across routes.
 */

import { useCallback } from "react"
import { motion } from "framer-motion"
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
  if (path === "/ai" || path.startsWith("/ai/")) return false
  // Onboarding is a full-screen setup flow; the floating pill covers its footer actions.
  if (/^\/(welcome|onboarding)(\/|$)/.test(path)) return false
  return true
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
        <motion.button
          ref={focusOnMount}
          drag
          dragMomentum={false}
          dragElastic={0.08}
          whileDrag={{ scale: 1.015 }}
          type="button"
          onClick={handleOpen}
          data-gravitre-ai-helper=""
          data-gravitre-ai-dock={onBuilder ? "canvas" : "workspace"}
          className={cn(
            // One launcher, one size, everywhere: a compact ink card parked in a
            // corner. It floats over the page; nothing reserves a band for it.
            "dark fixed z-40 flex touch-none cursor-grab items-center gap-3 rounded-[12px] border border-[color:var(--g-frame-rule)] text-left text-foreground",
            "max-md:bottom-[calc(56px+env(safe-area-inset-bottom)+12px)] md:bottom-5",
            // Pack actions occupy the space directly above mobile navigation.
            // Match only while that bar is mounted, without shifting other routes.
            "max-md:[:root:has([data-gravitre-mobile-action-dock])_&]:bottom-[calc(56px+env(safe-area-inset-bottom)+76px)]",
            "max-lg:[:root:has([data-testid=approval-mobile-actions])_&]:bottom-[calc(56px+env(safe-area-inset-bottom)+84px)]",
            onBuilder
              ? "left-5 md:left-[calc(var(--np-sidebar-rail)+12px)] md:[:root:has([data-nav-expanded=true])_&]:left-[calc(var(--np-sidebar)+12px)]"
              : "right-5 md:right-6",
            onBuilder ? "xl:w-[244px]" : "sm:w-[244px]",
            "min-h-[52px] p-2 sm:min-h-[60px] sm:py-2.5 sm:pl-2.5 sm:pr-3",
            // Ink command card: part of the graphite frame, not a support bubble.
            "bg-[color:var(--g-frame)] shadow-[0_12px_28px_-14px_rgb(0_0_0/0.55)] transition-colors",
            "active:cursor-grabbing hover:border-white/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--g-brand)]/40",
          )}
          aria-label={accessibleName}
          aria-expanded={false}
        >
          <span className="relative flex size-9 shrink-0 items-center justify-center rounded-[9px] bg-[color:var(--g-brand)]/15 text-[color:var(--g-brand)]">
            {orbActive ? (
              <GravitreOrb
                speaker={helperOrbSpeaker(presence)}
                className="!h-9 !w-9"
                amplitude={presence === "listening" ? 0.55 : 0.35}
              />
            ) : (
              // A conversation bubble, not the abstract agent glyph: the control
              // has to read as "AI Chat" at a glance.
              <NucleoChat className="h-4 w-4" />
            )}
            <span
              className={cn(
                "absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full border-2 border-[color:var(--g-frame)]",
                GRAVITRE_HELPER_PRESENCE_DOT[presence],
                (presence === "thinking" || presence === "executing") && "animate-pulse",
              )}
              aria-hidden
            />
          </span>
          <span
            data-gravitre-ai-helper-label=""
            className={cn(
              "hidden min-w-0 flex-1 flex-col items-stretch gap-0.5",
              onBuilder ? "xl:flex" : "sm:flex",
            )}
          >
            <span className="flex min-w-0 items-center justify-between gap-2">
              <span className="truncate text-[13px] font-semibold leading-tight text-foreground">
                {onBuilder ? "Gravitre AI" : "Ask Gravitre"}
              </span>
              {pendingApprovals > 0 ? (
                <span
                  className="inline-flex shrink-0 items-center gap-1 rounded-full bg-[color:var(--g-approval)]/15 px-1.5 text-[10.5px] font-medium tabular-nums leading-4 text-[color:var(--g-approval)]"
                  aria-hidden
                >
                  {pendingApprovals} to approve
                </span>
              ) : routeLabel && !onBuilder ? (
                <span
                  className="shrink-0 truncate rounded-[4px] border border-[color:var(--g-frame-rule)] px-1.5 font-mono text-[10px] leading-4 text-muted-foreground"
                  aria-hidden
                >
                  {routeLabel}
                </span>
              ) : null}
            </span>
            <span className={cn("truncate text-[11px] font-medium leading-tight", copy.tone)}>
              {helperStatus}
            </span>
          </span>
        </motion.button>
      </TooltipTrigger>
      <TooltipContent side="top">AI Chat</TooltipContent>
    </Tooltip>
  )
}
