/**
 * Desktop release manifest — single source for marketing download version + URLs.
 * Served from /desktop/latest.json (copied from public/ or rewritten by CI on release).
 */

export type DesktopPlatformKey = "macos" | "windows" | "linux"

export type DesktopDownload = {
  url: string
  label: string
  filename?: string
}

export type DesktopReleaseManifest = {
  version: string
  publishedAt?: string
  downloads: Record<DesktopPlatformKey, DesktopDownload>
}

export const DESKTOP_RELEASE_FALLBACK: DesktopReleaseManifest = {
  version: "0.1.0",
  publishedAt: "2026-08-10T00:00:00.000Z",
  downloads: {
    macos: {
      url: "https://github.com/cesarbohjr/gravitre-saas-backend/releases/latest/download/Gravitre_0.1.0_aarch64.dmg",
      label: "macOS",
      filename: "Gravitre_0.1.0_aarch64.dmg",
    },
    windows: {
      url: "https://github.com/cesarbohjr/gravitre-saas-backend/releases/latest/download/Gravitre_0.1.0_x64_en-US.msi",
      label: "Windows",
      filename: "Gravitre_0.1.0_x64_en-US.msi",
    },
    linux: {
      url: "https://github.com/cesarbohjr/gravitre-saas-backend/releases/latest/download/Gravitre_0.1.0_amd64.AppImage",
      label: "Linux",
      filename: "Gravitre_0.1.0_amd64.AppImage",
    },
  },
}

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
