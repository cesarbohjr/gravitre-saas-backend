/**
 * Chrome Web Store listing URL, from `NEXT_PUBLIC_CHROME_WEB_STORE_URL` on Vercel.
 *
 * Only set it once the listing is publicly installable (Public or Unlisted and
 * approved). Until then the install CTA points at the setup guide and the zip
 * below, never at a store page that says "This item is not available".
 *
 * Do not use Chrome Web Store Dev Console URLs (…/devconsole/…) — those require
 * Google sign-in and are not installable by customers.
 */
export const CHROME_WEB_STORE_URL = (process.env.NEXT_PUBLIC_CHROME_WEB_STORE_URL || "").trim()

/** Load-unpacked pack, refreshed by .github/workflows/extension-release.yml. */
export const EXTENSION_ZIP_URL =
  "https://github.com/cesarbohjr/gravitre-saas-backend/releases/download/extension-latest/gravitre-extension.zip"

export const EXTENSION_SETUP_GUIDE_HREF = "/docs/guides/how-to/browser-extension"

export function hasChromeWebStoreListing(): boolean {
  return /^https:\/\/(chromewebstore\.google\.com|chrome\.google\.com\/webstore)\//i.test(
    CHROME_WEB_STORE_URL,
  )
}

/** Primary install CTA — store when published, otherwise setup guide. */
export function extensionInstallHref(): string {
  return hasChromeWebStoreListing() ? CHROME_WEB_STORE_URL : EXTENSION_SETUP_GUIDE_HREF
}

export function extensionInstallCtaLabel(): string {
  return hasChromeWebStoreListing() ? "Add to Chrome" : "Install guide"
}
