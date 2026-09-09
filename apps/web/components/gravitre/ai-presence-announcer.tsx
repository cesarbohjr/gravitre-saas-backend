"use client"

/**
 * GravitreAIPresenceAnnouncer — Phase 3 (B9 accessibility pass:
 * "Presentation-mode changes get an `aria-live` announcement, following the
 * existing pattern in `voice-session-presence.tsx`").
 *
 * Pattern confirmed by reading `components/gravitre/assistant/
 * voice-session-presence.tsx` directly: it wraps its state label in a
 * container with `role="status" aria-live="polite"`, and relies on the
 * text content changing to trigger the screen-reader announcement — no
 * separate announcer library or manual `aria-live` region toggling. This
 * component follows that exact pattern for `presentationMode` /
 * `floatWorkspaceOpen` changes instead of voice state.
 *
 * Mounted once in `app/layout.tsx` (always — independent of which shell,
 * if any, is currently rendered), so it correctly captures every
 * transition regardless of which route's `AiWorkspace` instance is
 * currently mounted (Float/Expanded/Fullscreen only render from within
 * `ai-workspace.tsx`, which is not always mounted — this announcer reads
 * directly from the shared provider, not from shell DOM presence).
 *
 * Visually hidden (`sr-only`) — this is an announcement, not a visible
 * status widget.
 */

import { useGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"
import { GRAVITRE_AI_FLOAT_ENABLED } from "@/lib/ai-workspace-flags"

const MODE_ANNOUNCEMENT: Record<string, string> = {
  helper: "Gravitre AI minimized to helper",
  float: "Gravitre AI window opened",
  expanded: "Gravitre AI workspace expanded",
  fullscreen: "Gravitre AI workspace, fullscreen",
}

export function GravitreAIPresenceAnnouncer() {
  const { presentationMode, floatWorkspaceOpen } = useGravitreAIWorkspace()

  if (!GRAVITRE_AI_FLOAT_ENABLED) return null

  const message = floatWorkspaceOpen
    ? MODE_ANNOUNCEMENT[presentationMode] ?? "Gravitre AI"
    : "Gravitre AI minimized to helper"

  return (
    <div role="status" aria-live="polite" className="sr-only" data-gravitre-ai-announcer="">
      {message}
    </div>
  )
}
