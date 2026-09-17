"use client"

import { useState } from "react"
import { AppShell } from "@/components/gravitre/app-shell"
import { AskGravitreComposer } from "@/components/intelligence/ask-gravitre-composer"
import {
  usePublishGravitreAISelection,
  type GravitreAISelectedEntity,
} from "@/components/gravitre/ai-workspace-provider"

/**
 * Playwright harness for UX Reset Phase 1B. Not a product surface.
 */
export default function AiWorkspaceProofPage() {
  const [selected, setSelected] = useState<GravitreAISelectedEntity | null>(null)
  usePublishGravitreAISelection(selected)

  return (
    <AppShell title="Relationships">
      <div className="px-[var(--np-page-pad-sm)] py-6 sm:px-[var(--np-page-pad)]" data-gravitre-proof-page="">
        <p className="text-xs font-medium uppercase tracking-[0.14em] text-[color:var(--g-text-tertiary)]">
          Learning
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Relationships</h1>
        <p className="mt-2 max-w-xl text-sm text-[color:var(--g-text-secondary)]">
          Underlying application page for compact-workspace proof. Not customer-facing.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            data-select-acme=""
            className="text-sm font-medium text-[color:var(--g-brand)] underline"
            onClick={() =>
              setSelected({ kind: "entity", id: "acme", label: "Acme Corporation" })
            }
          >
            Select Acme Corporation
          </button>
          <span data-selected-label="" className="text-sm text-[color:var(--g-text-secondary)]">
            {selected ? `Selected: ${selected.label}` : "No selection"}
          </span>
        </div>
        <div className="mt-6 max-w-xl">
          <AskGravitreComposer
            variant="map"
            suggestions={["What changed for Acme?", "Review recent activity"]}
            selected={selected}
          />
        </div>
      </div>
    </AppShell>
  )
}
