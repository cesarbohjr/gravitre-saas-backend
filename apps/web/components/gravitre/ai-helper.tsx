"use client"

/**
 * GravitreAIHelper — Phase 2 of the "Gravitre AI Agent Workspace" redesign.
 *
 * See docs/delivery/ai-agent-floating-workspace-architecture-2026-09-07.md
 * Part C6, phase row 2 ("Mount + Float, behind a flag") and Part C3's Phase 0
 * prototype (`apps/web/app/dev/ai-workspace-preview/_components/
 * ai-workspace-prototype.tsx`), whose visual pattern this reuses — but wired
 * to real state instead of mock state.
 *
 * Mounted exactly once, in `app/layout.tsx`, inside `GravitreAIWorkspaceProvider`
 * and gated by `GRAVITRE_AI_FLOAT_ENABLED` (default OFF — see
 * `lib/ai-workspace-flags.ts`). Renders nothing when the flag is off, so this
 * component being mounted is not itself a visible behavior change.
 *
 * Suppressed on `/ai` itself — mirrors the existing precedent in
 * `lib/meson-page-context.ts`'s `shouldShowMesonToolbar`, which already hides
 * the Meson toolbar on `/ai` for the same reason: `/ai` already IS the full
 * chat surface, so a second "open AI chat" entry point on that exact page
 * would be redundant, not a new capability.
 *
 * Product decision made here (Phase 2, safe default, not permanent — see the
 * architecture doc's open decision #4 and this task's own instructions):
 * clicking the Helper from any route OTHER than `/ai` sets `presentationMode`
 * to "float" AND navigates to `/ai`. This is a deliberate, disclosed
 * deviation from "Float floats visually over whatever page you were on" —
 * see `ai-workspace-float-bridge.tsx`'s file-level comment for the full
 * rationale (the real live `useChat` instance backing `/ai` only exists
 * while `/ai`'s page component is mounted; Phase 1 explicitly kept it there
 * rather than hoisting it into the provider, and hoisting it now would be a
 * large, high-risk refactor of a 2,500+ line, heavily-concurrently-edited
 * file — out of scope for this phase). Once `/ai` mounts with
 * `presentationMode === "float"` already set, it renders the SAME live
 * conversation inside the floating shell instead of its normal full-page
 * layout — so the user still ends up looking at their real, live
 * conversation, just reached via a navigation rather than an in-place
 * overlay.
 *
 * Phase 3 reassessment (per this phase's own task instructions): now that
 * Expanded/Fullscreen also need the live `/ai` conversation, the
 * "navigate to /ai first, then present in the target mode" pattern is kept
 * unchanged for Phase 3 too — full cross-route `useChat` hoisting is NOT
 * undertaken here. Reasoning: Expanded/Fullscreen are reached exclusively
 * via controls inside Float (`GravitreFloatingWorkspace`'s "Expand" button)
 * and inside the Expanded shell (its "Fullscreen" button) — see
 * `ai-workspace-shell-bridge.tsx`. Both of those controls only exist while
 * already rendering on `/ai` in Float/Expanded mode, which itself only
 * happens after this Helper's `handleOpen()` navigation below. So by
 * construction, nothing in Phase 3 needs `useChat` to be reachable from any
 * OTHER route than `/ai` — the same constraint Phase 2 already accepted.
 * Hoisting the 2,700+-line, heavily-concurrently-edited `AiWorkspace`'s
 * `useChat` instance into the root provider remains a large, separate,
 * higher-risk refactor whose cost is still disproportionate to what this
 * phase's UI work requires. See the Phase 3 delivery report for the full
 * disclosed decision.
 */

import { useRouter } from "next/navigation"
import { NucleoAgent } from "@/components/icons/nucleo/semantic"
import { cn } from "@/lib/utils"
import { GRAVITRE_AI_FLOAT_ENABLED } from "@/lib/ai-workspace-flags"
import { useGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"
import {
  deriveGravitreHelperPresence,
  GRAVITRE_HELPER_PRESENCE_COPY,
  GRAVITRE_HELPER_PRESENCE_DOT,
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

export function GravitreAIHelper() {
  const router = useRouter()
  const {
    pageContext,
    presentationMode,
    setPresentationMode,
    floatWorkspaceOpen,
    setFloatWorkspaceOpen,
    conversation,
    approval,
    voice,
  } = useGravitreAIWorkspace()

  if (!GRAVITRE_AI_FLOAT_ENABLED) return null
  if (!shouldShowGravitreAIHelper(pageContext.pathname)) return null
  // Already floating/expanded/fullscreen — don't show a redundant second
  // launcher on top of the window it would open. Phase 3: this used to
  // check `presentationMode === "float"` only; it now checks
  // `floatWorkspaceOpen` so it also hides while Expanded/Fullscreen are
  // active (see ai-workspace-provider.tsx's file comment on
  // `floatWorkspaceOpen` for why that's a distinct flag from
  // `presentationMode`).
  if (floatWorkspaceOpen) return null

  const presence = deriveGravitreHelperPresence({ conversation, approval, voice })
  const copy = GRAVITRE_HELPER_PRESENCE_COPY[presence]

  const handleOpen = () => {
    setPresentationMode("float")
    setFloatWorkspaceOpen(true)
    router.push("/ai")
  }

  return (
    <button
      type="button"
      onClick={handleOpen}
      data-gravitre-ai-helper=""
      className={cn(
        "fixed bottom-5 left-5 z-[85] flex items-center gap-2.5 rounded-full border border-divide",
        "bg-[color:var(--g-surface-1)] px-3 py-2 shadow-[var(--np-shadow)] transition-colors",
        "hover:bg-[color:var(--g-surface-2)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--g-brand)]/40",
      )}
      aria-label={`Open Gravitre AI — ${copy.label}`}
    >
      <span className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[color:var(--g-brand)] to-emerald-700 text-white">
        <NucleoAgent className="h-4 w-4" />
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
        <span className="text-xs font-semibold text-[color:var(--g-text-primary)]">Gravitre AI</span>
        <span className={cn("text-[11px] font-medium", copy.tone)}>{copy.label}</span>
      </span>
    </button>
  )
}
