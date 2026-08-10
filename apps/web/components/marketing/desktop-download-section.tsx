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
    blurb: "Apple Silicon & Intel · .dmg",
    Icon: Apple,
  },
  windows: {
    label: "Windows",
    blurb: "Windows 10/11 · .msi",
    Icon: Monitor,
  },
  linux: {
    label: "Linux",
    blurb: "AppImage · modern desktops",
    Icon: Terminal,
  },
}

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
    () => (["macos", "windows", "linux"] as const).map((key) => ({
      key,
      ...PLATFORM_META[key],
      href: manifest.downloads[key]?.url || "#",
    })),
    [manifest],
  )

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
          </p>
        </div>

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
          Installers publish from the desktop CI pipeline. Signed macOS/Windows builds require
          Apple Developer and Windows code-signing certificates (setup cost outside the app
          repo). Browser enrichment stays in the Chrome extension — not in Desktop.
        </p>
      </div>
    </section>
  )
}
