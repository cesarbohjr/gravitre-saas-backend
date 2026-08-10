/**
 * Desktop release manifest — single source for marketing download version + URLs.
 * Served from /desktop/latest.json (copied from public/ or rewritten by CI on release).
 *
 * Import the public JSON via a path relative to this file (not `@/../public/...`),
 * which Turbopack cannot resolve outside the `@/` alias root.
 */
import latestJson from "../public/desktop/latest.json"

export type DesktopPlatformKey = "macos" | "windows" | "linux"

export type DesktopDownload = {
  url: string
  label: string
  filename?: string
}

export type DesktopReleaseManifest = {
  version: string
  publishedAt?: string
  /** false for early unsigned CI builds; omit/true once signing is wired. */
  signed?: boolean
  releaseUrl?: string
  downloads: Record<DesktopPlatformKey, DesktopDownload>
  alsoAvailable?: {
    macosIntel?: DesktopDownload
    windowsMsi?: DesktopDownload
  }
}

/** Bundled at build time from `public/desktop/latest.json`. */
export const DESKTOP_RELEASE_MANIFEST =
  latestJson as DesktopReleaseManifest

/** Same as the public file when present; kept for callers that expect a named fallback. */
export const DESKTOP_RELEASE_FALLBACK: DesktopReleaseManifest =
  DESKTOP_RELEASE_MANIFEST

export async function fetchDesktopReleaseManifest(
  origin?: string,
): Promise<DesktopReleaseManifest> {
  const base = origin?.replace(/\/$/, "") || ""
  try {
    const res = await fetch(`${base}/desktop/latest.json`, {
      next: { revalidate: 60 },
      cache: "no-store",
    })
    if (!res.ok) return DESKTOP_RELEASE_FALLBACK
    const data = (await res.json()) as DesktopReleaseManifest
    if (!data?.version || !data.downloads?.macos || !data.downloads?.windows || !data.downloads?.linux) {
      return DESKTOP_RELEASE_FALLBACK
    }
    return data
  } catch {
    return DESKTOP_RELEASE_FALLBACK
  }
}

export function detectDesktopPlatform(
  userAgent: string | null | undefined,
): DesktopPlatformKey | null {
  const ua = (userAgent || "").toLowerCase()
  if (!ua) return null
  if (ua.includes("mac os") || ua.includes("macintosh")) return "macos"
  if (ua.includes("windows")) return "windows"
  if (ua.includes("linux") || ua.includes("x11")) return "linux"
  return null
}
