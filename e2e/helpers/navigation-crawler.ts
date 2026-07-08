import type { Locator, Page } from "@playwright/test"
import { expect } from "@playwright/test"

export type NavigationProbeResult = {
  sourcePage: string
  linkText: string
  targetHref: string
  finalUrl: string
  pass: boolean
  reason?: string
  httpErrors: string[]
  consoleErrors: string[]
}

type DiscoveredLink = {
  href: string
  text: string
  locator: Locator
}

const SKIP_HREF_PREFIXES = ["mailto:", "tel:", "javascript:", "#", "data:"]

function isIgnorableConsoleError(line: string): boolean {
  if (line.includes("favicon")) return true
  if (line.includes("_vercel/insights")) return true
  if (line.includes("vercel-insights")) return true
  if (line.includes("va.vercel-scripts.com")) return true
  if (line.includes("vercel-scripts.com")) return true
  if (line.includes("Content Security Policy")) return true
  if (line.includes("Refused to execute script") && line.includes("MIME type")) return true
  if (line.includes("Failed to load resource") && line.includes("404")) return true
  return false
}

function normalizePath(url: string, origin: string): string {
  const parsed = new URL(url, origin)
  return parsed.pathname.replace(/\/+$/, "") || "/"
}

function isSameOriginHref(href: string, origin: string): boolean {
  if (!href || SKIP_HREF_PREFIXES.some((prefix) => href.startsWith(prefix))) return false
  try {
    const parsed = new URL(href, origin)
    return parsed.origin === origin
  } catch {
    return false
  }
}

async function mainContentText(page: Page): Promise<string> {
  const main = page.locator("main").first()
  if (await main.count()) {
    return ((await main.innerText()) || "").replace(/\s+/g, " ").trim()
  }
  return ((await page.locator("body").innerText()) || "").replace(/\s+/g, " ").trim()
}

async function discoverLinks(page: Page, origin: string, scope?: Locator): Promise<DiscoveredLink[]> {
  const root = scope ?? page.locator("body")
  const anchors = root.locator("a[href]")
  const count = await anchors.count()
  const seen = new Set<string>()
  const links: DiscoveredLink[] = []

  for (let index = 0; index < count; index += 1) {
    const locator = anchors.nth(index)
    const href = (await locator.getAttribute("href"))?.trim() ?? ""
    if (!isSameOriginHref(href, origin)) continue
    const absolute = new URL(href, origin).href
    const key = normalizePath(absolute, origin)
    if (seen.has(key)) continue
    seen.add(key)
    const text = ((await locator.innerText()) || href).replace(/\s+/g, " ").trim().slice(0, 120)
    links.push({ href, text: text || href, locator })
  }

  return links
}

function attachDiagnostics(page: Page) {
  const httpErrors: string[] = []
  const consoleErrors: string[] = []

  const onResponse = (response: { url: () => string; status: () => number; request: () => { resourceType: () => string } }) => {
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

export async function clickLinkAndVerify(options: {
  page: Page
  origin: string
  sourcePath: string
  link: DiscoveredLink
  expectedPathPrefix?: string
  minContentLength?: number
}): Promise<NavigationProbeResult> {
  const { page, origin, sourcePath, link, expectedPathPrefix, minContentLength = 40 } = options
  const diagnostics = attachDiagnostics(page)

  try {
    await page.goto(sourcePath, { waitUntil: "domcontentloaded" })
    const beforePath = normalizePath(page.url(), origin)

    const targetPath = normalizePath(new URL(link.href, origin).href, origin)
    const sourcePathNormalized = normalizePath(new URL(sourcePath, origin).href, origin)
    if (targetPath === sourcePathNormalized) {
      return {
        sourcePage: sourcePath,
        linkText: link.text,
        targetHref: targetPath,
        finalUrl: sourcePathNormalized,
        pass: true,
        reason: "Skipped same-page link",
        httpErrors: [],
        consoleErrors: [],
      }
    }

    const linkLocator = page.locator(`a[href="${link.href}"]`).filter({ hasText: link.text }).first()
    const clickable = (await linkLocator.count()) > 0 ? linkLocator : page.locator(`a[href="${link.href}"]`).first()

    await expect(clickable, `Link not found on ${sourcePath}: ${link.text}`).toBeVisible({ timeout: 15_000 })
    await clickable.click()
    await page.waitForLoadState("domcontentloaded")
    await page.waitForURL((url) => normalizePath(url.toString(), origin) !== beforePath, {
      timeout: 12_000,
    }).catch(() => undefined)
    await page.locator("main").first().waitFor({ state: "attached", timeout: 12_000 }).catch(() => undefined)
    await page.waitForTimeout(400)

    const finalUrl = page.url()
    const finalPath = normalizePath(finalUrl, origin)
    const content = await mainContentText(page)

    let pass = true
    let reason: string | undefined

    if (finalPath === beforePath) {
      pass = false
      reason = "URL did not change after click (possible no-op / broken client routing)"
    }
    if (expectedPathPrefix && !finalPath.startsWith(expectedPathPrefix)) {
      pass = false
      reason = `Expected path prefix ${expectedPathPrefix}, got ${finalPath}`
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
      sourcePage: sourcePath,
      linkText: link.text,
      targetHref: targetPath,
      finalUrl: finalPath,
      pass,
      reason,
      httpErrors: [...diagnostics.httpErrors],
      consoleErrors: [...diagnostics.consoleErrors],
    }
  } finally {
    diagnostics.detach()
  }
}

export async function crawlMarketingNavigation(options: {
  page: Page
  origin: string
  seedPaths?: string[]
  maxHomeLinks?: number
  maxHubLinksPerPage?: number
}): Promise<NavigationProbeResult[]> {
  const {
    page,
    origin,
    seedPaths = ["/"],
    maxHomeLinks = 35,
    maxHubLinksPerPage = 25,
  } = options

  const results: NavigationProbeResult[] = []

  for (const seedPath of seedPaths) {
    await page.goto(seedPath, { waitUntil: "domcontentloaded" })

    let links: DiscoveredLink[] = []
    if (seedPath === "/") {
      const regions = [page.locator("header"), page.locator("footer"), page.locator("main")]
      for (const region of regions) {
        if ((await region.count()) === 0) continue
        links.push(...(await discoverLinks(page, origin, region)))
      }
      const seen = new Set<string>()
      links = links.filter((link) => {
        const key = normalizePath(new URL(link.href, origin).href, origin)
        if (seen.has(key)) return false
        seen.add(key)
        return true
      })
    } else {
      links = await discoverLinks(page, origin, page.locator("main, body"))
    }

    const limit = seedPath === "/" ? maxHomeLinks : maxHubLinksPerPage
    for (const link of links.slice(0, limit)) {
      results.push(
        await clickLinkAndVerify({
          page,
          origin,
          sourcePath: seedPath,
          link,
        }),
      )
    }
  }

  return results
}

export function formatNavigationReport(results: NavigationProbeResult[]): string {
  const passed = results.filter((row) => row.pass)
  const failed = results.filter((row) => !row.pass)
  const lines = [
    `Navigation crawl: ${passed.length}/${results.length} passed`,
    "",
    ...failed.map(
      (row) =>
        `FAIL | ${row.sourcePage} → "${row.linkText}" → ${row.finalUrl} | ${row.reason ?? "unknown"}`,
    ),
  ]
  if (passed.length) {
    lines.push("", "Passes:")
    for (const row of passed.slice(0, 20)) {
      lines.push(`PASS | ${row.sourcePage} → "${row.linkText}" → ${row.finalUrl}`)
    }
    if (passed.length > 20) {
      lines.push(`… ${passed.length - 20} more passes`)
    }
  }
  return lines.join("\n")
}
