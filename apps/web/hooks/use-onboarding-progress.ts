"use client"

import useSWR from "swr"
import { fetcher } from "@/lib/fetcher"
import {
  ONBOARDING_CHECKLIST_STEP_KEYS,
  type OnboardingChecklistStepKey,
} from "@/lib/onboarding-checklist-steps"
import type { OnboardingProgress } from "@/types/api"

const LEGACY_WELCOME_KEYS = new Set(["role", "ready", "success"])

function completedChecklistKeys(progress: OnboardingProgress | undefined): Set<OnboardingChecklistStepKey> {
  const completed = new Set<OnboardingChecklistStepKey>()
  for (const step of progress?.steps ?? []) {
    if (!step.is_completed) continue
    const key = step.key as OnboardingChecklistStepKey
    if (ONBOARDING_CHECKLIST_STEP_KEYS.includes(key)) {
      completed.add(key)
    }
    if (LEGACY_WELCOME_KEYS.has(step.key)) {
      completed.add("welcome")
    }
  }
  if (progress?.welcome_completed) {
    completed.add("welcome")
  }
  return completed
}

export function useOnboardingProgress() {
  const { data, mutate, isLoading } = useSWR<OnboardingProgress>(
    "/api/onboarding",
    fetcher,
    { revalidateOnFocus: false },
  )

  const completedKeys = completedChecklistKeys(data)
  const completedCount = ONBOARDING_CHECKLIST_STEP_KEYS.filter((key) => completedKeys.has(key)).length
  const totalCount = ONBOARDING_CHECKLIST_STEP_KEYS.length
  const progress = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0
  const isComplete = Boolean(data?.welcome_completed || data?.completed_at || data?.skipped)

  return {
    data,
    mutate,
    isLoading,
    completedCount,
    totalCount,
    progress,
    isComplete,
  }
}
