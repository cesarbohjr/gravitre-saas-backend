import { test, expect } from "@playwright/test"
import { mkdirSync } from "node:fs"

const OUT = "e2e/artifacts/ux30-plus-harness"

/** UX/UI 3.0 Plus harness — no auth; safe against prod harness route. */
const shots: { name: string; path: string; width: number; height: number }[] = [
  { name: "foundation-default", path: "/dev/ai-workspace-preview?s=foundation&scene=default", width: 1280, height: 800 },
  { name: "foundation-reduced", path: "/dev/ai-workspace-preview?s=foundation&scene=reduced", width: 1280, height: 800 },
  { name: "intelligence-default", path: "/dev/ai-workspace-preview?s=intelligence&scene=default", width: 1440, height: 900 },
  { name: "intelligence-selected", path: "/dev/ai-workspace-preview?s=intelligence&scene=selected", width: 1440, height: 900 },
  { name: "intelligence-inspector", path: "/dev/ai-workspace-preview?s=intelligence&scene=inspector", width: 1440, height: 900 },
  { name: "intelligence-ai-context", path: "/dev/ai-workspace-preview?s=intelligence&scene=ai-context", width: 1440, height: 900 },
  { name: "intelligence-loading", path: "/dev/ai-workspace-preview?s=intelligence&scene=loading", width: 1440, height: 900 },
  { name: "intelligence-empty", path: "/dev/ai-workspace-preview?s=intelligence&scene=empty", width: 1440, height: 900 },
  { name: "intelligence-error", path: "/dev/ai-workspace-preview?s=intelligence&scene=error", width: 1440, height: 900 },
  { name: "intelligence-mobile", path: "/dev/ai-workspace-preview?s=intelligence&scene=mobile", width: 390, height: 844 },
  { name: "intelligence-reduced", path: "/dev/ai-workspace-preview?s=intelligence&scene=reduced", width: 1440, height: 900 },
  { name: "activity-default", path: "/dev/ai-workspace-preview?s=activity&scene=default", width: 1440, height: 900 },
  { name: "activity-timeline", path: "/dev/ai-workspace-preview?s=activity&scene=timeline", width: 1440, height: 900 },
  { name: "activity-fail", path: "/dev/ai-workspace-preview?s=activity&scene=fail", width: 1440, height: 900 },
  { name: "activity-selected", path: "/dev/ai-workspace-preview?s=activity&scene=selected", width: 1440, height: 900 },
  { name: "activity-inspector", path: "/dev/ai-workspace-preview?s=activity&scene=inspector", width: 1440, height: 900 },
  { name: "activity-ai-context", path: "/dev/ai-workspace-preview?s=activity&scene=ai-context", width: 1440, height: 900 },
  { name: "activity-loading", path: "/dev/ai-workspace-preview?s=activity&scene=loading", width: 1440, height: 900 },
  { name: "activity-empty", path: "/dev/ai-workspace-preview?s=activity&scene=empty", width: 1440, height: 900 },
  { name: "activity-error", path: "/dev/ai-workspace-preview?s=activity&scene=error", width: 1440, height: 900 },
  { name: "activity-mobile", path: "/dev/ai-workspace-preview?s=activity&scene=mobile", width: 390, height: 844 },
  { name: "activity-reduced", path: "/dev/ai-workspace-preview?s=activity&scene=reduced", width: 1440, height: 900 },
  { name: "navigation-compact", path: "/dev/ai-workspace-preview?s=navigation&scene=compact", width: 1280, height: 800 },
  { name: "navigation-expanded", path: "/dev/ai-workspace-preview?s=navigation&scene=expanded", width: 1280, height: 800 },
  { name: "navigation-pinned", path: "/dev/ai-workspace-preview?s=navigation&scene=pinned", width: 1280, height: 800 },
  { name: "navigation-keyboard", path: "/dev/ai-workspace-preview?s=navigation&scene=keyboard", width: 1280, height: 800 },
  { name: "navigation-mobile", path: "/dev/ai-workspace-preview?s=navigation&scene=mobile", width: 390, height: 844 },
]

test.describe("UX/UI 3.0 Plus harness — screenshot matrix", () => {
  test("all Cesar-selection surfaces render with review markers", async ({ page }) => {
    test.setTimeout(300_000)
    mkdirSync(OUT, { recursive: true })

    for (const shot of shots) {
      await page.setViewportSize({ width: shot.width, height: shot.height })
      await page.goto(shot.path, { waitUntil: "domcontentloaded" })
      await expect(page.getByText("UX/UI 3.0 Plus · harness only · not production")).toBeVisible({
        timeout: 30_000,
      })
      const surface = shot.path.match(/[?&]s=([^&]+)/)?.[1] ?? "unknown"
      await expect(page.locator(`[data-review-surface="${surface}"]`)).toBeVisible({ timeout: 30_000 })
      await page.screenshot({ path: `${OUT}/${shot.name}.png`, fullPage: true })
    }
  })
})
