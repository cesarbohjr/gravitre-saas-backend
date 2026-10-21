import { describe, expect, it } from "vitest"
import { manifestFromGithubReleases } from "@/lib/desktop-release"

const BASE = "https://github.com/cesarbohjr/gravitre-saas-backend/releases/download"

function release(tag: string, opts: { draft?: boolean; names?: string[] } = {}) {
  const version = tag.replace(/^desktop-v/, "")
  const names = opts.names ?? [
    `Gravitre_${version}_aarch64.dmg`,
    `Gravitre_${version}_x64.dmg`,
    `Gravitre_${version}_x64-setup.exe`,
    `Gravitre_${version}_x64_en-US.msi`,
    `Gravitre_${version}_amd64.AppImage`,
    "Gravitre_x64.app.tar.gz",
  ]
  return {
    tag_name: tag,
    html_url: `https://github.com/cesarbohjr/gravitre-saas-backend/releases/tag/${tag}`,
    draft: opts.draft ?? false,
    prerelease: false,
    published_at: "2026-10-21T19:00:00Z",
    assets: names.map((name) => ({ name, browser_download_url: `${BASE}/${tag}/${name}` })),
  }
}

describe("manifestFromGithubReleases", () => {
  it("uses the newest published desktop release, skipping drafts and other tags", () => {
    const manifest = manifestFromGithubReleases([
      release("desktop-v0.3.0", { draft: true }),
      { ...release("extension-latest"), assets: [] },
      release("desktop-v0.2.0"),
      release("desktop-v0.1.0"),
    ])
    expect(manifest?.version).toBe("0.2.0")
    expect(manifest?.downloads.windows.url).toBe(
      `${BASE}/desktop-v0.2.0/Gravitre_0.2.0_x64-setup.exe`,
    )
    expect(manifest?.downloads.macos.filename).toBe("Gravitre_0.2.0_aarch64.dmg")
    expect(manifest?.downloads.linux.filename).toBe("Gravitre_0.2.0_amd64.AppImage")
    expect(manifest?.alsoAvailable?.macosIntel?.filename).toBe("Gravitre_0.2.0_x64.dmg")
    expect(manifest?.alsoAvailable?.windowsMsi?.filename).toBe("Gravitre_0.2.0_x64_en-US.msi")
  })

  it("returns null when an installer is missing so the bundled manifest stays", () => {
    expect(
      manifestFromGithubReleases([
        release("desktop-v0.2.0", { names: ["Gravitre_0.2.0_aarch64.dmg"] }),
      ]),
    ).toBeNull()
    expect(manifestFromGithubReleases([])).toBeNull()
  })
})
