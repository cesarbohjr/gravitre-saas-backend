"use client"

/**
 * GravitreAIWorkspaceProvider — Phase 1 of the AI Agent Workspace redesign.
 *
 * See docs/delivery/ai-agent-floating-workspace-architecture-2026-09-07.md
 * (Part B3, Part C6 "1. State-hoisting refactor") for the approved plan this
 * file implements.
 *
 * This provider is mounted exactly once, in `app/layout.tsx`, ABOVE every
 * per-page `<AppShell>` instance (see architecture doc Finding A5 — AppShell
 * is remounted on every route change; this provider must not be). That means
 * its own React state — `presentationMode`, `pageContext`, and the
 * conversation/approval/voice *snapshots* published into it — survives
 * navigation between `/ai`, `/agents/[id]/chat`, and every other route.
 *
 * Phase 1 scope, deliberately narrow:
 *  - `presentationMode` exists with a real setter, but nothing reads it to
 *    change rendering yet. It defaults to "expanded" because that is what
 *    today's full-page `/ai` and `/agents/[id]/chat` routes already are —
 *    changing this default would be a visible behavior change, which this
 *    phase forbids. Helper/Float/Fullscreen chrome is Phase 2/3.
 *  - `pageContext` is genuinely new capability (nothing captured "what page
 *    the user is on" before this). It is intentionally kept separate from
 *    conversation state (architecture doc B3) — reading it never mutates the
 *    active conversation, and nothing today reads it to alter the UI.
 *  - `conversation` / `approval` / `voice` are *snapshots* published by
 *    whichever route/component currently owns the real `useChat` / voice /
 *    approval hooks (still instantiated per-route today, in
 *    `AiWorkspace` and `AgentChatPage`, because those two routes have
 *    genuinely different configurations — unified vs. agent-scoped — and
 *    forcing one shared `useChat` instance across both would be new,
 *    unapproved behavior, not a pure refactor). The extracted
 *    `GravitreAIConversation` components in `ai-conversation-core.tsx` are
 *    the single place that publishes these snapshots, so any future
 *    Helper/Float shell (Phase 2+) has one canonical place to read "what is
 *    the currently active conversation" without prop-drilling.
 *
 * No Redux/Zustand — React Context + the existing hook patterns, per the
 * architecture doc's B3 recommendation.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"
import { usePathname, useParams } from "next/navigation"
import { GRAVITRE_AI_FLOAT_ENABLED } from "@/lib/ai-workspace-flags"
import { modeToRemember, restoreTargetMode } from "@/lib/chat-window-state"
import type { UIMessage } from "ai"
import type { ChatModality } from "@/components/gravitre/assistant/voice-mode-toggle"
import type { VoicePresenceState } from "@/components/gravitre/assistant/voice-session-presence"
import type {
  ChatExecutionResult,
  ChatPendingTask,
} from "@/components/gravitre/assistant/chat-execution-panel"

/**
 * "helper" | "float" | "fullscreen" are scaffolding for Phase 2/3 — see the
 * architecture doc Part C6. Only "expanded" is meaningful today.
 */
export type GravitrePresentationMode = "helper" | "float" | "expanded" | "fullscreen"

export interface GravitreAIPageContext {
  /** Current route pathname, e.g. "/ai" or "/agents/42/chat". */
  pathname: string
  /** Current dynamic route params, e.g. { id: "42" } for /agents/[id]/chat. */
  params: Record<string, string | string[] | undefined>
}

export interface GravitreAIConversationSnapshot {
  /** Which route published this snapshot — "/ai" or "/agents/[id]/chat". */
  routeKey: string
  activeConversationId: string | null
  conversationTitle: string
  messages: UIMessage[]
  status: "ready" | "submitted" | "streaming" | "error"
  isStreaming: boolean
  isBusy: boolean
}

export interface GravitreAIApprovalSnapshot {
  dialogueMode: string | null
  pendingTask: ChatPendingTask | null
  executionResult: ChatExecutionResult | null
  confirmExecuting: boolean
}

export interface GravitreAIVoiceSnapshot {
  modality: ChatModality
  presence: VoicePresenceState
  presenceDetail?: string
  billing: boolean
}

export interface GravitreAIWorkspaceContextValue {
  /** Stable for the lifetime of this provider instance — see
   * __tests__/gravitre/ai-workspace-provider.test.ts for the mutation-proof
   * check that this does NOT change across simulated route navigation. */
  instanceId: string
  presentationMode: GravitrePresentationMode
  setPresentationMode: (mode: GravitrePresentationMode) => void
  /**
   * Phase 3 addition. `presentationMode`'s default value is the literal
   * string `"expanded"` (see the file header above and
   * `__tests__/gravitre/ai-workspace-provider.test.ts`'s
   * "defaults presentationMode to 'expanded'" test) — that value has meant
   * "today's normal full-page `/ai` (or `/agents/[id]/chat`), no special
   * chrome" since Phase 1, when no `presentationMode` value had any
   * rendering consequence yet.
   *
   * Phase 3 gives `"expanded"`/`"fullscreen"` a real rendering consequence
   * for the first time (`GravitreAIWorkspaceShell`). `floatWorkspaceOpen` is
   * a separate, explicit "is the floating workspace currently active" flag
   * so `GravitreAIWorkspaceShell` (and the Float bridge) can render on top
   * of the normal full-page layout without conflating that with
   * `presentationMode`'s own "expanded" default.
   *
   * Architecture doc Part B's "Open decision #4" ("do direct `/ai` visits
   * open the floating workspace in Expanded mode?") was explicitly left open
   * through Phase 3–5 (Phase 5 shipped with the answer "no, keep `/ai` as a
   * plain full-page embed"). Cesar revisited that call on 2026-09-09 after
   * seeing Phase 5 live — see this file's `useEffect` below — and chose
   * "yes": a direct `/ai` visit now auto-opens the Expanded shell, the same
   * chrome reached from any other page's Helper → Float → Expand. This is
   * still not the *only* way to reach `/ai`'s content — closing the shell
   * (or navigating there with the shell already explicitly closed this
   * session) falls back to the pre-Phase-5 full-page embed, unchanged.
   */
  floatWorkspaceOpen: boolean
  setFloatWorkspaceOpen: (open: boolean) => void
  /**
   * The mode to come back to when the launcher reopens the chat.
   *
   * Without this, closing to the launcher set the mode to "expanded" regardless
   * of what the user was in, and the launcher then always opened "float": a user
   * working in fullscreen came back to a small window, and a user in a small
   * window could not be returned to it. Never "helper", since restoring to the
   * launcher would look like the click did nothing.
   */
  previousPresentationMode: GravitrePresentationMode
  /** Records the current mode as the restore target, then closes to the launcher. */
  minimizeToHelper: () => void
  /** Reopens at the remembered mode rather than always at "float". */
  restoreFromHelper: () => void
  pageContext: GravitreAIPageContext
  conversation: GravitreAIConversationSnapshot | null
  setConversation: (snapshot: GravitreAIConversationSnapshot | null) => void
  approval: GravitreAIApprovalSnapshot | null
  setApproval: (snapshot: GravitreAIApprovalSnapshot | null) => void
  voice: GravitreAIVoiceSnapshot | null
  setVoice: (snapshot: GravitreAIVoiceSnapshot | null) => void
}

const GravitreAIWorkspaceContext = createContext<GravitreAIWorkspaceContextValue | null>(null)

function createInstanceId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID()
  }
  return `gravitre-ai-workspace-${Math.random().toString(36).slice(2)}-${Date.now()}`
}

export function GravitreAIWorkspaceProvider({ children }: { children: ReactNode }) {
  const instanceIdRef = useRef<string | null>(null)
  if (!instanceIdRef.current) instanceIdRef.current = createInstanceId()

  const [presentationMode, setPresentationMode] = useState<GravitrePresentationMode>("expanded")
  const [floatWorkspaceOpen, setFloatWorkspaceOpenState] = useState(false)
  const [conversation, setConversation] = useState<GravitreAIConversationSnapshot | null>(null)
  const [approval, setApproval] = useState<GravitreAIApprovalSnapshot | null>(null)
  const [voice, setVoice] = useState<GravitreAIVoiceSnapshot | null>(null)

  // Tracks whether the user has explicitly closed the floating workspace at
  // least once this session (via `setFloatWorkspaceOpen(false)` — the shell
  // bridges' "Close to helper" control is the only caller of that today).
  // The auto-open effect below checks this so closing the shell on `/ai`
  // sticks for the rest of the session instead of immediately reopening on
  // the next render/navigation. A fresh page load resets it, which is the
  // intended "default experience" behavior, not a bug.
  const explicitlyClosedRef = useRef(false)

  const setFloatWorkspaceOpen = useCallback((open: boolean) => {
    explicitlyClosedRef.current = !open
    setFloatWorkspaceOpenState(open)
  }, [])

  const [previousPresentationMode, setPreviousPresentationMode] =
    useState<GravitrePresentationMode>("float")

  const minimizeToHelper = useCallback(() => {
    // Capture before closing. The old closeToHelper() overwrote the mode with
    // "expanded" first, which destroyed the only record of where to return to.
    setPresentationMode((current) => {
      setPreviousPresentationMode(modeToRemember(current))
      return current
    })
    setFloatWorkspaceOpen(false)
  }, [setFloatWorkspaceOpen])

  const restoreFromHelper = useCallback(() => {
    setPresentationMode(restoreTargetMode(previousPresentationMode))
    setFloatWorkspaceOpen(true)
  }, [previousPresentationMode, setFloatWorkspaceOpen])

  // usePathname/useParams are safe this high in the tree — OnboardingChecklist
  // (also mounted directly in app/layout.tsx) already relies on the same
  // Next.js App Router behavior.
  const pathname = usePathname() ?? ""
  const rawParams = useParams()
  const pageContext = useMemo<GravitreAIPageContext>(
    () => ({ pathname, params: (rawParams ?? {}) as Record<string, string | string[] | undefined> }),
    [pathname, rawParams],
  )

  const onAiRoute = pathname === "/ai" || pathname.startsWith("/ai/")

  // Cesar's 2026-09-09 decision (resolving architecture doc Open decision
  // #4): a direct `/ai` visit auto-opens the same Expanded shell reached
  // from every other page's Helper → Float → Expand, instead of staying a
  // plain full-page embed. Gated on the flag for consistency with every
  // other float-workspace behavior in this file's tree, and on
  // `explicitlyClosedRef` so an explicit close sticks for the session (see
  // that ref's comment above).
  useEffect(() => {
    if (!GRAVITRE_AI_FLOAT_ENABLED) return
    if (!onAiRoute) return
    if (floatWorkspaceOpen) return
    if (explicitlyClosedRef.current) return
    setFloatWorkspaceOpenState(true)
    setPresentationMode("expanded")
  }, [onAiRoute, floatWorkspaceOpen])

  const value = useMemo<GravitreAIWorkspaceContextValue>(
    () => ({
      instanceId: instanceIdRef.current as string,
      presentationMode,
      setPresentationMode,
      floatWorkspaceOpen,
      setFloatWorkspaceOpen,
      previousPresentationMode,
      minimizeToHelper,
      restoreFromHelper,
      pageContext,
      conversation,
      setConversation,
      approval,
      setApproval,
      voice,
      setVoice,
    }),
    [
      presentationMode,
      floatWorkspaceOpen,
      setFloatWorkspaceOpen,
      previousPresentationMode,
      minimizeToHelper,
      restoreFromHelper,
      pageContext,
      conversation,
      approval,
      voice,
    ],
  )

  return (
    <GravitreAIWorkspaceContext.Provider value={value}>
      {children}
    </GravitreAIWorkspaceContext.Provider>
  )
}

/**
 * Consume the shared Gravitre AI workspace context. Throws outside a
 * `GravitreAIWorkspaceProvider` so a missing mount (e.g. a future route
 * rendered outside `app/layout.tsx`'s tree) fails loudly instead of silently
 * falling back to per-component local state.
 */
export function useGravitreAIWorkspace(): GravitreAIWorkspaceContextValue {
  const ctx = useContext(GravitreAIWorkspaceContext)
  if (!ctx) {
    throw new Error(
      "useGravitreAIWorkspace() must be used within a GravitreAIWorkspaceProvider. " +
        "It is mounted once in apps/web/app/layout.tsx — if you see this error, " +
        "something is rendering outside that tree.",
    )
  }
  return ctx
}
