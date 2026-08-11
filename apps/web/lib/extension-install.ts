/**
 * Chrome Web Store listing URL.
 *
 * Prefer `NEXT_PUBLIC_CHROME_WEB_STORE_URL` on Vercel. Falls back to the published
 * public listing for extension id `iegkidilloajngolbpgfkaeglblnklol`.
 *
 * Do not use Chrome Web Store Dev Console URLs (…/devconsole/…) — those require
 * Google sign-in and are not installable by customers.
 */
export const PUBLISHED_CHROME_WEB_STORE_URL =
  "https://chromewebstore.google.com/detail/gravitre/iegkidilloajngolbpgfkaeglblnklol"

export const CHROME_WEB_STORE_URL = (
  process.env.NEXT_PUBLIC_CHROME_WEB_STORE_URL || PUBLISHED_CHROME_WEB_STORE_URL
).trim()

export function hasChromeWebStoreListing(): boolean {
  return /^https:\/\/(chromewebstore\.google\.com|chrome\.google\.com\/webstore)\//i.test(
    CHROME_WEB_STORE_URL,
  )
}

/** Primary install CTA — store when published, otherwise setup guide. */
export function extensionInstallHref(): string {
  return hasChromeWebStoreListing()
    ? CHROME_WEB_STORE_URL
    : "/docs/guides/how-to/browser-extension"
}

export function extensionInstallCtaLabel(): string {
  return hasChromeWebStoreListing() ? "Add to Chrome" : "Install guide"
}
