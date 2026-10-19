"use client"

import { Route } from "lucide-react"
import { MemoryEntityEmbeddingsSettings } from "@/components/settings/memory-entity-embeddings-settings"
import { SOURCE_GOVERNANCE_UI_ENABLED, SourceGovernanceSettings } from "@/components/settings/source-governance-settings"
import { SetHeader, SetIco } from "./settings-kit"
import "./aimodels-settings.css"

/**
 * Settings > Workspace > AI models (design p12). Model routing is managed by
 * Gravitre (no workspace default-model API exists, so nothing here pretends to
 * save one); chat entity matching is the real Memory opt-in.
 */
export function AIModelsSettings({ isAdmin }: { isAdmin: boolean }) {
  return (
    <>
      <SetHeader
        crumb="Settings / Workspace"
        title="AI models"
        description="How Gravitre picks models for your agents, and how chat memory matches the people and channels you mention."
      />
      <section className="gs-card aimodels-routing" aria-label="Model routing">
        <div className="aimodels-routing-copy">
          <div className="top">
            <SetIco icon={Route} />
            <div>
              <b>Model routing</b>
              <span>Managed by Gravitre for every workspace</span>
            </div>
          </div>
          <p>
            Each task goes to the model that fits it best. Quick lookups use a fast model, reasoning and writing use a
            deeper one. Workspace level overrides are not available yet, so nothing here can drift from what actually
            runs.
          </p>
        </div>
        <div className="aimodels-diagram" role="img" aria-label="Routing example: a task goes to the fast model for lookups and routing, or the deep model for reasoning and writing">
          <div className="task">Task</div>
          <svg className="flow" width="60" height="70" viewBox="0 0 60 70" aria-hidden>
            <path className="gs-flow" d="M2 35 C 30 35, 30 12, 58 12" stroke="var(--gs-green-bright)" fill="none" strokeWidth="1.6" strokeDasharray="4 4" />
            <path className="gs-flow" d="M2 35 C 30 35, 30 58, 58 58" stroke="var(--gs-ghost)" fill="none" strokeWidth="1.6" strokeDasharray="4 4" />
          </svg>
          <div className="lanes">
            <div className="lane fast">
              <strong>Fast</strong> <span>lookups, routing</span>
            </div>
            <div className="lane">
              <strong>Deep</strong> <span>reasoning, writing</span>
            </div>
          </div>
        </div>
      </section>
      <MemoryEntityEmbeddingsSettings isAdmin={isAdmin} />
      {SOURCE_GOVERNANCE_UI_ENABLED ? <SourceGovernanceSettings isAdmin={isAdmin} /> : null}
    </>
  )
}
