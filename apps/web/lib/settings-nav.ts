"use client"

import { useRouter } from "next/navigation"
import { settingsHrefForSection, type SettingsSectionId } from "@/lib/settings-sections"

/** Shared navigation for SettingsShell sub-routes (billing, approvals, permissions). */
export function useSettingsSectionNav(current: SettingsSectionId) {
  const router = useRouter()

  return (section: SettingsSectionId) => {
    if (section === current) return
    router.push(settingsHrefForSection(section))
  }
}
