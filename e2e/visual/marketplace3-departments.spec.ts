import { test, expect } from "@playwright/test"
import fixtures from "../../apps/web/app/e2e/shots/marketplace3/fixtures.json"

for (const width of [1440, 390]) {
  for (const [slug, workspace] of Object.entries(fixtures)) {
    test(`${slug} at ${width}px: contracts, tabs and empty evidence`, async ({ page }) => {
      const errors: string[] = []
      page.on("pageerror", error => errors.push(error.message))
      await page.setViewportSize({ width, height: 1000 })
      await page.emulateMedia({ reducedMotion: "reduce" })
      await page.goto(`/e2e/shots/marketplace3/${slug}`, { waitUntil: "networkidle" })
      await expect(page.getByRole("heading", { name: workspace.asset.title, exact: true })).toBeVisible()
      for (const name of ["Overview", "Plays", "Evidence", "Data & standards", "Agents & activity"]) {
        await page.getByRole("tab", { name, exact: true }).click()
        await expect(page.getByRole("tabpanel")).toBeVisible()
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
        if (name === "Plays") {
          await page.getByRole("searchbox").fill("zzzznotfound")
          await expect(page.getByText("No Plays match your search.")).toBeVisible()
          await page.getByRole("searchbox").fill("")
        }
        if (name === "Evidence") await expect(page.getByText("No verified business measurements are available for this pack.")).toBeVisible()
      }
      expect(errors).toEqual([])
      await page.screenshot({ path: test.info().outputPath(`${slug}-${width}.png`), fullPage: true })
    })
  }
  test(`rollout at ${width}px: all previews and stale proof gate`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 })
    await page.emulateMedia({ reducedMotion: "reduce" })
    await page.goto("/e2e/shots/marketplace3/rollout", { waitUntil: "networkidle" })
    for (const workspace of Object.values(fixtures)) {
      await page.getByRole("button").filter({ hasText: workspace.asset.title }).click()
      await expect(page.getByRole("button", { name: "Publish verified pack" })).toBeDisabled()
      await expect(page.getByText("Stored certification differs from current resolved proof. Publication uses the fresh evidence gate.")).toBeVisible()
      await page.getByRole("button", { name: "Preview department" }).click()
      await expect(page.getByRole("dialog").getByRole("heading", { name: workspace.asset.title, exact: true })).toBeVisible()
      await page.keyboard.press("Escape")
    }
  })
}
