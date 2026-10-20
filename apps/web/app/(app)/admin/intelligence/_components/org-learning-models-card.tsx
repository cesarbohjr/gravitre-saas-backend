"use client"

import { LearningCapabilitiesPanel } from "@/components/intelligence/learning-capabilities-panel"

export function OrgLearningModelsCard({ enabled }: { enabled: boolean }) {
  return <LearningCapabilitiesPanel enabled={enabled} technicalInventory />
}
