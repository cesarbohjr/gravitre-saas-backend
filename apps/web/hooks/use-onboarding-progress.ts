"use client"

import useSWR from "swr"
import { fetcher } from "@/lib/fetcher"
import type { OnboardingProgress } from "@/types/api"

export function useOnboardingProgress() {
  const { data, mutate, isLoading } = useSWR<OnboardingProgress>(
    "/api/onboarding",
    fetcher,
    { revalidateOnFocus: false },
  )

  const completedCount = data?.steps?.filter((step) => step.is_completed).length ?? 0
  const totalCount = data?.steps?.length ?? 0
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
