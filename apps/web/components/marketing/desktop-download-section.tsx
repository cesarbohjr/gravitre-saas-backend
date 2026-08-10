"use client"

import { useEffect, useMemo, useState } from "react"
import { motion } from "framer-motion"
import { Apple, Download, Monitor, Terminal } from "lucide-react"
import {
  DESKTOP_RELEASE_FALLBACK,
  detectDesktopPlatform,
  type DesktopPlatformKey,
  type DesktopReleaseManifest,
} from "@/lib/desktop-release"

const PLATFORM_META: Record<
  DesktopPlatformKey,
  { label: string; blurb: string; Icon: typeof Apple }
> = {
  macos: {
    label: "macOS",
    blurb: "Apple Silicon · .dmg",
    Icon: Apple,
  },
  windows: {
    label: "Windows",
    blurb: "Windows 10/11 · setup.exe",
    Icon: Monitor,
  },
  linux: {
    label: "Linux",
    blurb: "AppImage · modern desktops",
    Icon: Terminal,
  },
}

const RELEASE_PAGE =
  "https://github.com/cesarbohjr/gravitre-saas-backend/releases/tag/desktop-v0.1.0"
const MAC_INTEL_DMG =
  "https://github.com/cesarbohjr/gravitre-saas-backend/releases/download/desktop-v0.1.0/Gravitre_0.1.0_x64.dmg"

type Props = {
  initialManifest?: DesktopReleaseManifest
  className?: string
}

/**
 * Marketing download block — three OS options, smart highlight, version from
 * /desktop/latest.json (same file CI should rewrite on release).
 */
export function DesktopDownloadSection({
  initialManifest = DESKTOP_RELEASE_FALLBACK,
  className,
}: Props) {
  const [manifest, setManifest] = useState(initialManifest)
  const [detected, setDetected] = useState<DesktopPlatformKey | null>(null)

  useEffect(() => {
    setDetected(detectDesktopPlatform(navigator.userAgent))
    let cancelled = false
    ;(async () => {
      try {
        const res = await fetch("/desktop/latest.json", { cache: "no-store" })
        if (!res.ok) return
        const data = (await res.json()) as DesktopReleaseManifest
        if (!cancelled && data?.version && data.downloads) setManifest(data)
      } catch {
        // Keep SSR/fallback manifest.
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const platforms = useMemo(
    () =>
      (["macos", "windows", "linux"] as const).map((key) => ({
        key,
        ...PLATFORM_META[key],
        href: manifest.downloads[key]?.url || "#",
      })),
    [manifest],
  )

  const releaseUrl = manifest.releaseUrl || RELEASE_PAGE
  const intelUrl = manifest.alsoAvailable?.macosIntel?.url || MAC_INTEL_DMG
  const isUnsigned = manifest.signed !== true

  return (
    <section className={className ?? "relative py-24 sm:py-32 bg-white border-t border-zinc-200"}>
      <div className="mx-auto max-w-7xl px-6">
        <div className="mx-auto max-w-2xl text-center mb-12">
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2">
            <Download className="h-4 w-4 text-emerald-600" />
            <span className="text-sm font-medium text-emerald-700">Desktop companion</span>
          </div>
          <h2 className="text-4xl sm:text-5xl font-bold tracking-tight text-zinc-900 text-balance">
            Download Gravitre Desktop
          </h2>
          <p className="mt-4 text-lg text-zinc-600">
            Summon chat, glanceable activity, and approvals from a global shortcut — without
            hunting for a browser tab. Full Settings, Meson, Agents, and Billing stay on the web.
          </p>
          <p className="mt-3 text-sm font-medium text-zinc-500">
            Version <span className="text-zinc-800">v{manifest.version}</span>
            {manifest.publishedAt ? (
              <span className="text-zinc-400">
                {" "}
                · {new Date(manifest.publishedAt).toLocaleDateString()}
              </span>
            ) : null}
            {isUnsigned ? (
              <span className="text-amber-700"> · unsigned early builds</span>
            ) : null}
          </p>
        </div>

        {isUnsigned ? (
          <div
            role="note"
            aria-label="Unsigned build security warnings"
            className="mx-auto mb-10 max-w-3xl border border-amber-300 bg-amber-50 px-5 py-5 text-left sm:px-6"
          >
            <p className="text-sm font-semibold text-amber-950">
              These are early, unsigned builds
            </p>
            <p className="mt-2 text-sm leading-relaxed text-amber-950/90">
              We have not yet provisioned Apple or Windows code-signing certificates. On first
              launch, Windows and macOS will show a real security warning. That is expected for
              this release — not malware, and not something we are hiding. Signed installers are a
              separate follow-up once credentials are in place.
            </p>
            <div className="mt-4 space-y-3 text-sm leading-relaxed text-amber-950/90">
              <div>
                <p className="font-semibold text-amber-950">Windows — “Windows protected your PC”</p>
                <p className="mt-1">
                  SmartScreen may block the installer. Click <strong>More info</strong>, then{" "}
                  <strong>Run anyway</strong>. Only do this if you downloaded from this page or the
                  official GitHub release linked below.
                </p>
              </div>
              <div>
                <p className="font-semibold text-amber-950">
                  macOS — “Apple could not verify…” / cannot be opened
                </p>
                <p className="mt-1">
                  Gatekeeper blocks unsigned apps. In Finder, <strong>right-click</strong> (or
                  Control-click) the app → <strong>Open</strong> → confirm{" "}
                  <strong>Open</strong> again. Or: System Settings → Privacy &amp; Security → scroll
                  to the blocked app → <strong>Open Anyway</strong>.
                </p>
              </div>
            </div>
            <p className="mt-4 text-xs text-amber-900/80">
              Release assets:{" "}
              <a
                href={releaseUrl}
                className="font-medium underline underline-offset-2 hover:text-amber-950"
                target="_blank"
                rel="noopener noreferrer"
              >
                desktop-v0.1.0 on GitHub
              </a>
              . Intel Macs: use{" "}
              <a
                href={intelUrl}
                className="font-medium underline underline-offset-2 hover:text-amber-950"
              >
                Gravitre_0.1.0_x64.dmg
              </a>
              .
            </p>
          </div>
        ) : null}

        <div className="grid gap-4 sm:grid-cols-3">
          {platforms.map((platform, index) => {
            const highlighted = detected === platform.key
            const Icon = platform.Icon
            return (
              <motion.a
                key={platform.key}
                href={platform.href}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.05 }}
                className={[
                  "group relative flex flex-col items-start rounded-2xl border p-6 transition-colors",
                  highlighted
                    ? "border-emerald-300 bg-emerald-50/70 shadow-sm"
                    : "border-zinc-200 bg-zinc-50/60 hover:border-zinc-300 hover:bg-white",
                ].join(" ")}
              >
                {highlighted ? (
                  <span className="absolute right-4 top-4 rounded-full bg-emerald-600 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white">
                    Your OS
                  </span>
                ) : null}
                <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl border border-zinc-200 bg-white text-zinc-800">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="text-lg font-semibold text-zinc-900">{platform.label}</h3>
                <p className="mt-1 text-sm text-zinc-600">{platform.blurb}</p>
                <span className="mt-5 inline-flex items-center gap-1.5 text-sm font-semibold text-zinc-900 group-hover:text-emerald-700">
                  Download
                  <Download className="h-3.5 w-3.5" />
                </span>
              </motion.a>
            )
          })}
        </div>

        <p className="mx-auto mt-8 max-w-2xl text-center text-xs text-zinc-500">
          Browser enrichment stays in the Chrome extension — not in Desktop. Full Settings, Meson,
          Agents, and Billing open in the browser from the companion.
        </p>
      </div>
    </section>
  )
}
