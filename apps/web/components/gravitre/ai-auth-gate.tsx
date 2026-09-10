"use client"

/**
 * The single authentication boundary for the Gravitre AI assistant.
 *
 * Before this existed, nothing in the assistant tree asked who the visitor was.
 * The assistant was kept off the marketing site by `RootProviders` reading the
 * `x-gravitre-marketing` request header and choosing `MarketingProviders` over
 * `AppProviders`. That is a routing decision, not an authentication decision, and
 * it left three separate ways for an anonymous visitor to reach authenticated AI
 * UI:
 *
 *   1. `GravitreAIHelper` rendered the launcher wherever `AppProviders` mounted,
 *      and `shouldShowGravitreAIHelper("/")` returns true by design.
 *   2. `GravitreAIWorkspaceHost` armed itself on any `/ai*` pathname, mounting the
 *      entire `AiWorkspace` surface.
 *   3. `GravitreAIShortcutListener` bound the keyboard shortcut globally, so the
 *      assistant could be opened programmatically with no session at all.
 *
 * All three now sit behind this one gate, so there is exactly one place to reason
 * about and exactly one place to change. Children are *not rendered* rather than
 * hidden: on logout the whole subtree unmounts, which is what actually destroys
 * the ephemeral conversation UI, stops in-flight authenticated requests, and
 * removes prior conversation text from the DOM. Hiding with CSS would have left
 * all three in place.
 *
 * This gate is a client-side rendering decision and is deliberately *not* the
 * security boundary. Every protected AI endpoint must reject unauthenticated
 * requests on its own; this only stops us from showing and offering UI that the
 * visitor has no right to use.
 */

import { useEffect, useRef, type ReactNode } from "react"
import { useAuth } from "@/lib/auth-context"
import { useGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"
import { purgeStoredConversationState } from "@/lib/ai-conversation-storage"

/**
 * `loading` counts as not-allowed on purpose. Treating an unresolved session as
 * permitted is what produces a flash of authenticated UI on a cold load, and it
 * is the same default that would keep the assistant on screen through a logout.
 * Appearing a moment late is the strictly safer failure.
 */
export function isGravitreAIAllowed(args: { hasSession: boolean; loading: boolean }): boolean {
  if (args.loading) return false
  return args.hasSession
}

export function GravitreAIAuthGate({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const { floatWorkspaceOpen, setFloatWorkspaceOpen } = useGravitreAIWorkspace()
  const allowed = isGravitreAIAllowed({ hasSession: Boolean(user?.id), loading })
  const wasAllowedRef = useRef(false)

  // The provider lives above this gate (it has to — it wraps the whole app so
  // float state survives route changes), so unmounting the children does not by
  // itself clear `floatWorkspaceOpen`. Without this, logging out and back in
  // would silently reopen the assistant to whatever was on screen before.
  useEffect(() => {
    if (!allowed && floatWorkspaceOpen) {
      setFloatWorkspaceOpen(false)
    }
  }, [allowed, floatWorkspaceOpen, setFloatWorkspaceOpen])

  // Unmounting clears the DOM, not the machine. The thread id lives in
  // localStorage and the message cache in sessionStorage, so without this the
  // previous user's conversation stayed readable after logout.
  //
  // Fires only on a real allowed -> not-allowed transition, never on first paint:
  // a cold load starts unauthenticated while the session resolves, and purging
  // there would wipe the returning user's own cache before they were let in.
  useEffect(() => {
    if (loading) return
    if (wasAllowedRef.current && !allowed) {
      purgeStoredConversationState()
    }
    wasAllowedRef.current = allowed
  }, [allowed, loading])

  if (!allowed) return null
  return <>{children}</>
}
