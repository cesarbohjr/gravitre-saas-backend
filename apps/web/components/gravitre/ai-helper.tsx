"use client"

/**
 * GravitreAIHelper — Phase 2–5 of the "Gravitre AI Agent Workspace" redesign.
 *
 * Phase 5: opens Float in place (no `router.push("/ai")`). The root-mounted
 * AiWorkspace host owns the live useChat instance across routes.
 */

import { NucleoChat } from "@/components/icons/nucleo/semantic"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { GravitreOrb } from "@/components/gravitre/assistant/voice-presentation"
import { cn } from "@/lib/utils"
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

function helperOrbSpeaker(presence: GravitreHelperPresence): "user" | "agent" {
  if (presence === "listening") return "user"
  return "agent"
}

export function GravitreAIHelper() {
  const {
    pageContext,
    floatWorkspaceOpen,
    restoreFromHelper,
    conversation,
    approval,
    voice,
  } = useGravitreAIWorkspace()
  const { user, loading } = useAuth()

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

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={handleOpen}
          data-gravitre-ai-helper=""
          className={cn(
            "fixed left-5 z-[85] flex items-center gap-2.5 rounded-full border border-divide",
            "max-md:bottom-[calc(56px+env(safe-area-inset-bottom)+12px)] md:bottom-5",
            "bg-[color:var(--g-surface-1)] px-3 py-2 shadow-[var(--np-shadow)] transition-colors",
            "hover:bg-[color:var(--g-surface-2)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--g-brand)]/40",
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
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-[color:var(--g-brand)] to-emerald-700 text-white">
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
          <span className="hidden flex-col items-start pr-1 sm:flex">
            <span className="text-xs font-semibold text-[color:var(--g-text-primary)]">
              Gravitre AI
            </span>
            <span className={cn("text-[11px] font-medium", copy.tone)}>{copy.label}</span>
          </span>
        </button>
      </TooltipTrigger>
      <TooltipContent side="right">AI Chat</TooltipContent>
    </Tooltip>
  )
}
