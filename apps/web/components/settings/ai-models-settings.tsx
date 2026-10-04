"use client"

import { MemoryEntityEmbeddingsSettings } from "@/components/settings/memory-entity-embeddings-settings"

export function AIModelsSettings({ isAdmin }: { isAdmin: boolean }) {
  return (
    <div className="space-y-6" aria-label="AI model settings">
      <div className="rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-4">
        <h3 className="text-sm font-medium">Workspace model defaults</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          There is no organization API for workspace default models, use-case defaults, fallback models, or model-override policies.
          Those controls were removed so this form cannot show a saved state that is not persisted.
        </p>
      </div>
      <MemoryEntityEmbeddingsSettings isAdmin={isAdmin} />
    </div>
  )
}
