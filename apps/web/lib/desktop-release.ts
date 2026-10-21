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

const DESKTOP_RELEASES_API =
  "https://api.github.com/repos/cesarbohjr/gravitre-saas-backend/releases?per_page=20"

type GithubReleaseAsset = { name: string; browser_download_url: string }
type GithubRelease = {
  tag_name: string
  html_url: string
  draft: boolean
  prerelease: boolean
  published_at: string | null
  assets: GithubReleaseAsset[]
}

function pickAsset(
  assets: GithubReleaseAsset[],
  test: (name: string) => boolean,
  label: string,
): DesktopDownload | undefined {
  const asset = assets.find((a) => test(a.name))
  return asset ? { url: asset.browser_download_url, label, filename: asset.name } : undefined
}

/**
 * Build a manifest from the newest published `desktop-v*` GitHub release, so
 * /download follows CI releases without a web redeploy. Returns null when the
 * release is missing any primary installer (callers keep the bundled manifest).
 */
export function manifestFromGithubReleases(
  releases: GithubRelease[],
): DesktopReleaseManifest | null {
  const release = releases.find(
    (r) => !r.draft && !r.prerelease && r.tag_name.startsWith("desktop-v"),
  )
  if (!release) return null
  const assets = release.assets || []
  const macos = pickAsset(assets, (n) => /_aarch64\.dmg$/.test(n), "macOS (Apple Silicon)")
  const windows = pickAsset(assets, (n) => /_x64-setup\.exe$/.test(n), "Windows")
  const linux = pickAsset(assets, (n) => /\.AppImage$/.test(n), "Linux")
  if (!macos || !windows || !linux) return null
  return {
    version: release.tag_name.replace(/^desktop-v/, ""),
    publishedAt: release.published_at || undefined,
    signed: DESKTOP_RELEASE_MANIFEST.signed,
    releaseUrl: release.html_url,
    downloads: { macos, windows, linux },
    alsoAvailable: {
      macosIntel: pickAsset(assets, (n) => /_x64\.dmg$/.test(n), "macOS (Intel)"),
      windowsMsi: pickAsset(assets, (n) => /\.msi$/.test(n), "Windows (.msi)"),
    },
  }
}

/** Browser-side lookup of the newest desktop release; null on any failure. */
export async function fetchLatestGithubDesktopRelease(): Promise<DesktopReleaseManifest | null> {
  try {
    const res = await fetch(DESKTOP_RELEASES_API, {
      headers: { Accept: "application/vnd.github+json" },
      cache: "no-store",
    })
    if (!res.ok) return null
    return manifestFromGithubReleases((await res.json()) as GithubRelease[])
  } catch {
    return null
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
