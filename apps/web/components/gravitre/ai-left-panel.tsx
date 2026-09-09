"use client"

/**
 * GravitreAILeftPanel — Phase 3 of the "Gravitre AI Agent Workspace"
 * redesign.
 *
 * See docs/delivery/ai-agent-floating-workspace-architecture-2026-09-07.md
 * Part B2: "GravitreAILeftPanel | = existing ConversationSidebar, reused
 * as-is | none [new work required]."
 *
 * Verified directly against the current `ConversationSidebar`
 * (`components/gravitre/assistant/conversation-sidebar.tsx`) before writing
 * this: its props are a plain, self-contained callback/data interface (no
 * dependency on being physically inside `AiWorkspace`'s specific DOM tree),
 * and on `md:` and wider (the only breakpoints in scope for Phase 3 — mobile
 * sheet is Phase 4) it renders `md:static` rather than a fixed overlay
 * drawer, so it drops cleanly into a normal flex-row layout. This file is a
 * deliberately trivial passthrough — not a fork — kept as its own named
 * component (rather than importing `ConversationSidebar` directly at each
 * call site) purely so `GravitreAIWorkspaceShell`'s callers have one stable
 * name to depend on if the underlying component is ever swapped.
 */

import { ConversationSidebar } from "@/components/gravitre/assistant/conversation-sidebar"

export type GravitreAILeftPanelProps = Parameters<typeof ConversationSidebar>[0]

export function GravitreAILeftPanel(props: GravitreAILeftPanelProps) {
  return <ConversationSidebar {...props} />
}
