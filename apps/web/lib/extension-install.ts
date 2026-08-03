/**
 * Chrome Web Store listing URL — set NEXT_PUBLIC_CHROME_WEB_STORE_URL when the
 * real listing (or unlisted beta) is live. Empty means install via setup guide
 * (load unpacked / org-distributed Chromium pack).
 */
export const CHROME_WEB_STORE_URL = (
  process.env.NEXT_PUBLIC_CHROME_WEB_STORE_URL || ""
).trim()

export function hasChromeWebStoreListing(): boolean {
  return /^https:\/\/chromewebstore\.google\.com\//i.test(CHROME_WEB_STORE_URL)
}

/** Primary install CTA — store when published, otherwise setup guide. */
export function extensionInstallHref(): string {
  return hasChromeWebStoreListing()
    ? CHROME_WEB_STORE_URL
    : "/docs/guides/how-to/browser-extension"
}

export function extensionInstallCtaLabel(): string {
  return hasChromeWebStoreListing()
    ? "Install from Chrome Web Store"
    : "Install guide (Chrome beta)"
}
