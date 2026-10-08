"use client"

import { EngineSettingsTab as RetrievalEngineSettings } from "./engine-settings-tab"
import { OrgLearningModelsCard } from "./org-learning-models-card"
import { ChatPersonaSettingsCard } from "./chat-persona-settings-card"

export function EngineTab({ enabled }: { enabled: boolean }) {
  if (!enabled) return null

  return (
    <div className="space-y-6">
      <ChatPersonaSettingsCard enabled={enabled} />
      <OrgLearningModelsCard enabled={enabled} />
      <RetrievalEngineSettings enabled={enabled} />
    </div>
  )
}
