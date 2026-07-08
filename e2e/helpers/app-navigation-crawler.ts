import type { Locator, Page } from "@playwright/test"
import { expect } from "@playwright/test"

import type { AppNavItem } from "./app-navigation-items"
import {
  formatNavigationReport,
  type NavigationProbeResult,
} from "./navigation-crawler"

function normalizePath(url: string, origin: string): string {
  const parsed = new URL(url, origin)
  return parsed.pathname.replace(/\/+$/, "") || "/"
}

function attachDiagnostics(page: Page) {
  const httpErrors: string[] = []
  const consoleErrors: string[] = []

  const onResponse = (response: {
    url: () => string
    status: () => number
    request: () => { resourceType: () => string }
  }) => {
    const status = response.status()
    const type = response.request().resourceType()
    if (type === "document" && status >= 400) {
      httpErrors.push(`${status} ${response.url()}`)
    }
  }
  const onConsole = (message: { type: () => string; text: () => string }) => {
    if (message.type() === "error") {
      consoleErrors.push(message.text())
    }
  }

  page.on("response", onResponse)
  page.on("console", onConsole)

  return {
    detach: () => {
      page.off("response", onResponse)
      page.off("console", onConsole)
    },
    httpErrors,
    consoleErrors,
  }
}

function isIgnorableConsoleError(line: string): boolean {
  if (line.includes("favicon")) return true
  if (line.includes("_vercel/insights")) return true
  if (line.includes("vercel-insights")) return true
  if (line.includes("va.vercel-scripts.com")) return true
  if (line.includes("vercel-scripts.com")) return true
  if (line.includes("Content Security Policy")) return true
  if (line.includes("Refused to execute script") && line.includes("MIME type")) return true
  if (line.includes("Failed to load resource") && line.includes("404")) return true
  if (line.includes("socket hang up")) return true
  if (line.includes("response_feedback")) return true
  if (line.includes("logo_url does not exist")) return true
  if (line.includes("APIResponse") && line.includes("error")) return true
  return false
}

async function mainContentText(page: Page): Promise<string> {
  const main = page.locator("main").first()
  if (await main.count()) {
    return ((await main.innerText()) || "").replace(/\s+/g, " ").trim()
  }
  return ((await page.locator("body").innerText()) || "").replace(/\s+/g, " ").trim()
}

async function ensureSidebarReady(page: Page, timeout = 15_000) {
  const sidebarNav = page.locator("aside nav")
  await sidebarNav.waitFor({ state: "visible", timeout })
  return sidebarNav
}

function sidebarLinkLocator(sidebarNav: Locator, item: AppNavItem) {
  const href = item.hash ? item.href : item.href.split("#")[0]
  return sidebarNav.locator(`a[href="${href}"]`).filter({ visible: true }).first()
}

export async function clickAppSidebarItem(options: {
  page: Page
  origin: string
  sourcePath: string
  item: AppNavItem
  minContentLength?: number
  resetToSeed?: boolean
}): Promise<NavigationProbeResult> {
  const { page, origin, sourcePath, item, minContentLength = 30, resetToSeed = true } = options
  const diagnostics = attachDiagnostics(page)

  try {
    if (resetToSeed) {
      await page.goto(sourcePath, { waitUntil: "domcontentloaded" })
      await ensureSidebarReady(page, 120_000)
    }
    const sidebarNav = await ensureSidebarReady(page)

    const beforePath = normalizePath(page.url(), origin)
    const beforeHash = new URL(page.url()).hash
    const targetPath = normalizePath(new URL(item.href, origin).href, origin)

    if (targetPath === beforePath) {
      if (item.hash) {
        if (beforeHash === item.hash) {
          return {
            sourcePage: resetToSeed ? sourcePath : beforePath,
            linkText: item.name,
            targetHref: item.hash ? `${targetPath}${item.hash}` : targetPath,
            finalUrl: beforePath + beforeHash,
            pass: true,
            reason: "Already on target page",
            httpErrors: [],
            consoleErrors: [],
          }
        }
      } else if (!beforeHash) {
        return {
          sourcePage: resetToSeed ? sourcePath : beforePath,
          linkText: item.name,
          targetHref: targetPath,
          finalUrl: beforePath,
          pass: true,
          reason: "Already on target page",
          httpErrors: [],
          consoleErrors: [],
        }
      }
    }

    const link = sidebarLinkLocator(sidebarNav, item)
    if (item.optional && (await link.count()) === 0) {
      return {
        sourcePage: sourcePath,
        linkText: item.name,
        targetHref: targetPath,
        finalUrl: beforePath,
        pass: true,
        reason: "Optional nav item not shown",
        httpErrors: [],
        consoleErrors: [],
      }
    }

    await expect(link, `Sidebar link missing: ${item.name} (${item.href})`).toBeVisible({
      timeout: 15_000,
    })
    try {
      await link.scrollIntoViewIfNeeded()
      const clickTarget = item.hash ? `${targetPath}${item.hash}` : targetPath
      await link.click({ timeout: 15_000 })

      await expect
        .poll(
          () => {
            const path = normalizePath(page.url(), origin)
            const hash = new URL(page.url()).hash
            if (!path.startsWith(item.expectedPathPrefix)) return ""
            if (item.hash) return hash === item.hash ? `${path}${hash}` : ""
            return path
          },
          { timeout: 20_000, message: `Expected navigation to ${clickTarget}` },
        )
        .not.toBe("")
    } catch (error) {
      const finalUrl = page.url()
      const finalPath = normalizePath(finalUrl, origin)
      const finalHash = new URL(finalUrl).hash
      return {
        sourcePage: resetToSeed ? sourcePath : beforePath,
        linkText: item.name,
        targetHref: item.hash ? `${targetPath}${item.hash}` : targetPath,
        finalUrl: item.hash ? `${finalPath}${finalHash}` : finalPath,
        pass: false,
        reason: error instanceof Error ? error.message : `Navigation failed for ${item.name}`,
        httpErrors: [...diagnostics.httpErrors],
        consoleErrors: [...diagnostics.consoleErrors],
      }
    }

    await page.waitForLoadState("domcontentloaded")
    await page.locator("main").first().waitFor({ state: "attached", timeout: 20_000 }).catch(() => undefined)
    await page.waitForTimeout(600)

    const finalUrl = page.url()
    const finalPath = normalizePath(finalUrl, origin)
    const finalHash = new URL(finalUrl).hash
    const content = await mainContentText(page)

    let pass = true
    let reason: string | undefined

    if (!finalPath.startsWith(item.expectedPathPrefix)) {
      pass = false
      reason = `Expected path prefix ${item.expectedPathPrefix}, got ${finalPath}`
    }
    if (item.hash) {
      if (finalHash !== item.hash) {
        pass = false
        reason = `Expected hash ${item.hash}, got ${finalHash || "(empty)"}`
      }
    } else if (finalPath === beforePath && beforeHash === finalHash) {
      pass = false
      reason = "URL did not change after sidebar click (frozen / no-op navigation)"
    }
    if (content.length < minContentLength) {
      pass = false
      reason = `Main content too short (${content.length} chars)`
    }
    if (diagnostics.httpErrors.length > 0) {
      pass = false
      reason = `Document HTTP error: ${diagnostics.httpErrors.join("; ")}`
    }
    const noisyConsole = diagnostics.consoleErrors.filter((line) => !isIgnorableConsoleError(line))
    if (noisyConsole.length > 0) {
      pass = false
      reason = `Console errors: ${noisyConsole.slice(0, 2).join(" | ")}`
    }

    return {
      sourcePage: resetToSeed ? sourcePath : beforePath,
      linkText: item.name,
      targetHref: item.hash ? `${targetPath}${item.hash}` : targetPath,
      finalUrl: item.hash ? `${finalPath}${finalHash}` : finalPath,
      pass,
      reason,
      httpErrors: [...diagnostics.httpErrors],
      consoleErrors: [...diagnostics.consoleErrors],
    }
  } finally {
    diagnostics.detach()
  }
}

export async function crawlAppSidebarNavigation(options: {
  page: Page
  origin: string
  items: AppNavItem[]
  seedPath?: string
  /** When true, reuse the current session (after prepareAdminAppSession) instead of reloading. */
  startFromCurrentPage?: boolean
}): Promise<NavigationProbeResult[]> {
  const { page, origin, items, seedPath = "/home", startFromCurrentPage = false } = options
  const results: NavigationProbeResult[] = []

  if (!startFromCurrentPage) {
    await page.goto(seedPath, { waitUntil: "domcontentloaded" })
  }
  await ensureSidebarReady(page, 120_000)

  for (const item of items) {
    results.push(
      await clickAppSidebarItem({
        page,
        origin,
        sourcePath: seedPath,
        item,
        resetToSeed: false,
      }),
    )
    await ensureSidebarReady(page, 15_000).catch(() => undefined)
  }

  return results
}

export { formatNavigationReport }
