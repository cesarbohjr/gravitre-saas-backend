import { test, expect } from "@playwright/test"
import { mkdirSync } from "node:fs"

const OUT = "e2e/artifacts/ux-reset-2-review"

const shots: { name: string; path: string; width: number; height: number }[] = [
  { name: "nucleo-scale", path: "/dev/ai-workspace-preview?s=nucleo&scene=default", width: 1280, height: 800 },
  { name: "ai-empty", path: "/dev/ai-workspace-preview?s=ai&scene=empty", width: 1280, height: 800 },
  { name: "ai-loading", path: "/dev/ai-workspace-preview?s=ai&scene=loading", width: 1280, height: 800 },
  { name: "ai-error", path: "/dev/ai-workspace-preview?s=ai&scene=error", width: 1280, height: 800 },
  { name: "ai-compact-conversation", path: "/dev/ai-workspace-preview?s=ai&scene=compact-conversation", width: 1280, height: 800 },
  { name: "ai-compact-voice-listen", path: "/dev/ai-workspace-preview?s=ai&scene=compact-voice-listen", width: 1280, height: 800 },
  { name: "ai-compact-voice-speak", path: "/dev/ai-workspace-preview?s=ai&scene=compact-voice-speak", width: 1280, height: 800 },
  { name: "ai-expanded-conversation", path: "/dev/ai-workspace-preview?s=ai&scene=expanded-conversation", width: 1440, height: 900 },
  { name: "ai-expanded-history", path: "/dev/ai-workspace-preview?s=ai&scene=expanded-history", width: 1440, height: 900 },
  { name: "ai-expanded-work", path: "/dev/ai-workspace-preview?s=ai&scene=expanded-work", width: 1440, height: 900 },
  { name: "ai-expanded-tool", path: "/dev/ai-workspace-preview?s=ai&scene=expanded-tool", width: 1440, height: 900 },
  { name: "ai-fullscreen-work", path: "/dev/ai-workspace-preview?s=ai&scene=fullscreen-work", width: 1728, height: 960 },
  { name: "ai-fullscreen-inspect", path: "/dev/ai-workspace-preview?s=ai&scene=fullscreen-inspect", width: 1728, height: 960 },
  { name: "ai-mobile-conversation", path: "/dev/ai-workspace-preview?s=ai&scene=mobile-conversation", width: 390, height: 844 },
  { name: "ai-mobile-work", path: "/dev/ai-workspace-preview?s=ai&scene=mobile-work", width: 390, height: 844 },
  { name: "ai-mobile-inspect", path: "/dev/ai-workspace-preview?s=ai&scene=mobile-inspect", width: 390, height: 844 },
  { name: "agents-team", path: "/dev/ai-workspace-preview?s=agents&scene=default", width: 1440, height: 900 },
  { name: "agents-selected", path: "/dev/ai-workspace-preview?s=agents&scene=selected", width: 1440, height: 900 },
  { name: "agents-list", path: "/dev/ai-workspace-preview?s=agents&scene=list", width: 1440, height: 900 },
  { name: "agents-graph", path: "/dev/ai-workspace-preview?s=agents&scene=graph", width: 1440, height: 900 },
  { name: "agents-empty", path: "/dev/ai-workspace-preview?s=agents&scene=empty", width: 1440, height: 900 },
  { name: "agents-mobile", path: "/dev/ai-workspace-preview?s=agents&scene=mobile", width: 390, height: 844 },
  { name: "rel-default", path: "/dev/ai-workspace-preview?s=relationships&scene=default", width: 1440, height: 900 },
  { name: "rel-selected", path: "/dev/ai-workspace-preview?s=relationships&scene=selected", width: 1440, height: 900 },
  { name: "rel-empty", path: "/dev/ai-workspace-preview?s=relationships&scene=empty", width: 1440, height: 900 },
  { name: "rel-loading", path: "/dev/ai-workspace-preview?s=relationships&scene=loading", width: 1440, height: 900 },
  { name: "rel-error", path: "/dev/ai-workspace-preview?s=relationships&scene=error", width: 1440, height: 900 },
  { name: "perf-default", path: "/dev/ai-workspace-preview?s=performance&scene=default", width: 1440, height: 900 },
  { name: "perf-empty", path: "/dev/ai-workspace-preview?s=performance&scene=empty", width: 1440, height: 900 },
  { name: "perf-loading", path: "/dev/ai-workspace-preview?s=performance&scene=loading", width: 1440, height: 900 },
  { name: "perf-error", path: "/dev/ai-workspace-preview?s=performance&scene=error", width: 1440, height: 900 },
  { name: "wf-default", path: "/dev/ai-workspace-preview?s=workflows&scene=default", width: 1440, height: 900 },
  { name: "wf-selected", path: "/dev/ai-workspace-preview?s=workflows&scene=selected", width: 1440, height: 900 },
  { name: "wf-empty", path: "/dev/ai-workspace-preview?s=workflows&scene=empty", width: 1440, height: 900 },
  { name: "wf-error", path: "/dev/ai-workspace-preview?s=workflows&scene=error", width: 1440, height: 900 },
  { name: "runs-outcome", path: "/dev/ai-workspace-preview?s=runs&scene=default", width: 1440, height: 900 },
  { name: "runs-trace", path: "/dev/ai-workspace-preview?s=runs&scene=selected", width: 1440, height: 900 },
  { name: "runs-empty", path: "/dev/ai-workspace-preview?s=runs&scene=empty", width: 1440, height: 900 },
  { name: "runs-error", path: "/dev/ai-workspace-preview?s=runs&scene=error", width: 1440, height: 900 },
  { name: "connectors-default", path: "/dev/ai-workspace-preview?s=connectors&scene=default", width: 1440, height: 900 },
  { name: "connectors-selected", path: "/dev/ai-workspace-preview?s=connectors&scene=selected", width: 1440, height: 900 },
  { name: "connectors-empty", path: "/dev/ai-workspace-preview?s=connectors&scene=empty", width: 1440, height: 900 },
  { name: "connectors-error", path: "/dev/ai-workspace-preview?s=connectors&scene=error", width: 1440, height: 900 },
]

test.describe("UX Reset 2.0 selected-direction review shots", () => {
  test("capture harness scenes", async ({ page }) => {
    test.setTimeout(300_000)
    mkdirSync(OUT, { recursive: true })
    for (const shot of shots) {
      await page.setViewportSize({ width: shot.width, height: shot.height })
      await page.goto(shot.path, { waitUntil: "domcontentloaded" })
      await expect(page.locator("[data-review-surface]")).toBeVisible({ timeout: 30_000 })
      await page.screenshot({ path: `${OUT}/${shot.name}.png`, fullPage: true })
    }
  })
})
