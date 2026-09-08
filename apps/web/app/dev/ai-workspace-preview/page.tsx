/**
 * PHASE 0 PROTOTYPE ROUTE — isolated, unlinked, mock-data only.
 *
 * Not in any nav, not in sitemap, not wired to real conversation/agent/voice
 * state. See docs/delivery/ai-agent-floating-workspace-architecture-2026-09-07.md
 * Part C3 for the plan this implements, and _components/ai-workspace-prototype.tsx
 * for the actual components.
 */

import type { Metadata } from "next"
import { AiWorkspacePrototype } from "./_components/ai-workspace-prototype"

export const metadata: Metadata = {
  title: "AI Workspace Preview (internal)",
  robots: { index: false, follow: false },
}

export default function AiWorkspacePreviewPage() {
  return <AiWorkspacePrototype />
}
