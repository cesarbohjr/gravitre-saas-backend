"use client"

import { useEffect, useMemo, useState, type ReactNode } from "react"
import { motion } from "framer-motion"
import {
  AlertTriangle,
  Download,
  Keyboard,
  MessageSquare,
  Shield,
  Sparkles,
} from "lucide-react"
import {
  DESKTOP_RELEASE_FALLBACK,
  detectDesktopPlatform,
  type DesktopPlatformKey,
  type DesktopReleaseManifest,
} from "@/lib/desktop-release"
import {
  AppleVendorIcon,
  LinuxVendorIcon,
  WindowsVendorIcon,
} from "@/components/marketing/os-vendor-icons"
import { GridBackground } from "@/components/marketing/home/grid-background"
import { DesktopCompanionPreview } from "@/components/marketing/desktop-companion-preview"

const RELEASE_PAGE =
  "https://github.com/cesarbohjr/gravitre-saas-backend/releases/tag/desktop-v0.1.0"
const MAC_INTEL_DMG =
  "https://github.com/cesarbohjr/gravitre-saas-backend/releases/download/desktop-v0.1.0/Gravitre_0.1.0_x64.dmg"

type PlatformMeta = {
  label: string
  blurb: string
  index: string
  footer: string
  footerHref?: string
  Icon: (props: { className?: string }) => ReactNode
  iconClassName: string
}

const PLATFORM_META: Record<DesktopPlatformKey, PlatformMeta> = {
  macos: {
    label: "macOS",
    blurb: "Apple Silicon · .dmg",
    index: "01",
    footer: "Intel Mac? Get the x64 build",
    footerHref: MAC_INTEL_DMG,
    Icon: AppleVendorIcon,
    iconClassName: "text-foreground",
  },
  windows: {
    label: "Windows",
    blurb: "Windows 10/11 · setup.exe",
    index: "02",
    footer: "64-bit only",
    Icon: WindowsVendorIcon,
    iconClassName: "",
  },
  linux: {
    label: "Linux",
    blurb: "AppImage · modern desktops",
    index: "03",
    footer: "x86_64 AppImage",
    Icon: LinuxVendorIcon,
    iconClassName: "text-foreground",
  },
}

const FLOATING_ICONS = [
  { Icon: Keyboard, className: "left-[6%] top-[18%]", delay: 0 },
  { Icon: MessageSquare, className: "right-[8%] top-[22%]", delay: 0.6 },
  { Icon: Shield, className: "left-[10%] top-[58%]", delay: 1.1 },
  { Icon: Sparkles, className: "right-[6%] top-[52%]", delay: 1.7 },
] as const

type Props = {
  initialManifest?: DesktopReleaseManifest
  className?: string
}

/**
 * Marketing download — light hero (shared with home), effects, companion mock, OS cards.
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

  const platforms = useMemo(() => {
    const intelUrl = manifest.alsoAvailable?.macosIntel?.url || MAC_INTEL_DMG
    return (["macos", "windows", "linux"] as const).map((key) => ({
      key,
      ...PLATFORM_META[key],
      href: manifest.downloads[key]?.url || "#",
      footerHref:
        key === "macos" ? intelUrl : PLATFORM_META[key].footerHref,
    }))
  }, [manifest])

  const releaseUrl = manifest.releaseUrl || RELEASE_PAGE
  const isUnsigned = manifest.signed !== true
  const publishedLabel = manifest.publishedAt
    ? new Date(manifest.publishedAt).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : null

  return (
    <section
      className={
        className ?? "relative overflow-hidden border-t border-border bg-card"
      }
    >
      {/* Same atmosphere language as home / extension — not the darker cream+green wash */}
      <GridBackground />

      {/* Floating accent icons (no Lottie logo marks) */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
        {FLOATING_ICONS.map(({ Icon, className: pos, delay }) => (
          <motion.div
            key={pos}
            className={`absolute hidden h-11 w-11 items-center justify-center rounded-2xl border border-border/70 bg-card/70 text-primary shadow-sm shadow-zinc-900/[0.04] backdrop-blur-sm lg:flex ${pos}`}
            animate={{ y: [0, -12, 0], opacity: [0.45, 0.85, 0.45] }}
            transition={{ duration: 5.5, delay, repeat: Infinity, ease: "easeInOut" }}
          >
            <Icon className="h-5 w-5" strokeWidth={1.5} />
          </motion.div>
        ))}
      </div>

      <div className="relative mx-auto max-w-6xl px-6 pb-20 pt-28 sm:pb-28 sm:pt-32">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
          className="mx-auto max-w-3xl text-center"
        >
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-border bg-card/90 px-4 py-2 shadow-sm shadow-zinc-900/[0.04] backdrop-blur-sm">
            <span className="h-1.5 w-1.5 rounded-full bg-primary/100" />
            <span className="text-sm font-medium text-primary">
              Desktop companion · Alt+Space
            </span>
          </div>

          <h1 className="text-balance text-4xl font-bold tracking-tight text-foreground sm:text-5xl lg:text-6xl">
            Gravitre,{" "}
            <span className="bg-gradient-to-r from-emerald-700 via-emerald-600 to-teal-600 bg-clip-text text-transparent">
              one shortcut away.
            </span>
          </h1>

          <p className="mx-auto mt-5 max-w-2xl text-pretty text-lg leading-relaxed text-muted-foreground sm:text-xl">
            A lightweight companion for chat, activity, and approvals — summon it from anywhere with
            a global shortcut. Settings, Meson, Agents, and Billing stay on the web.
          </p>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-2.5">
            <span className="inline-flex items-center rounded-full border border-border/80 bg-card px-3.5 py-1.5 text-sm font-medium text-foreground shadow-sm shadow-zinc-900/[0.04]">
              v{manifest.version}
            </span>
            {publishedLabel ? (
              <span className="inline-flex items-center rounded-full border border-border/80 bg-card px-3.5 py-1.5 text-sm font-medium text-foreground shadow-sm shadow-zinc-900/[0.04]">
                {publishedLabel}
              </span>
            ) : null}
            {isUnsigned ? (
              <span className="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-3.5 py-1.5 text-sm font-semibold text-amber-900">
                Unsigned early build
              </span>
            ) : null}
          </div>
        </motion.div>

        <div className="mt-14 sm:mt-16">
          <DesktopCompanionPreview />
        </div>

        {/* OS cards */}
        <div className="mt-16 grid gap-5 sm:grid-cols-3 sm:gap-6">
          {platforms.map((platform, index) => {
            const highlighted = detected === platform.key
            const Icon = platform.Icon
            return (
              <motion.div
                key={platform.key}
                initial={{ opacity: 0, y: 22 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-40px" }}
                transition={{ delay: 0.08 + index * 0.07, duration: 0.45 }}
                className={[
                  "relative flex flex-col rounded-[1.35rem] border bg-card/95 p-6 shadow-[0_18px_50px_-28px_rgba(24,24,27,0.35)] backdrop-blur-sm transition-transform duration-300 hover:-translate-y-0.5",
                  highlighted
                    ? "border-primary/30 ring-2 ring-emerald-400/35"
                    : "border-border/80",
                ].join(" ")}
              >
                <div className="mb-5 flex items-start justify-between gap-3">
                  <div
                    className={[
                      "flex h-14 w-14 items-center justify-center rounded-2xl border border-border bg-muted/50",
                      platform.iconClassName,
                    ].join(" ")}
                  >
                    <Icon className="h-7 w-7" />
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <span className="text-xs font-semibold tabular-nums tracking-wide text-muted-foreground">
                      {platform.index}
                    </span>
                    {highlighted ? (
                      <span className="rounded-full bg-primary px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white">
                        Your OS
                      </span>
                    ) : null}
                  </div>
                </div>

                <h2 className="text-xl font-semibold tracking-tight text-foreground">
                  {platform.label}
                </h2>
                <p className="mt-1.5 text-sm text-muted-foreground">{platform.blurb}</p>

                <a
                  href={platform.href}
                  className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-foreground px-4 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-foreground/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-500 focus-visible:ring-offset-2"
                >
                  <Download className="h-4 w-4" />
                  Download
                </a>

                {platform.footerHref ? (
                  <a
                    href={platform.footerHref}
                    className="mt-3 text-center text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
                  >
                    {platform.footer}
                  </a>
                ) : (
                  <p className="mt-3 text-center text-xs font-medium text-muted-foreground">
                    {platform.footer}
                  </p>
                )}
              </motion.div>
            )
          })}
        </div>

        {isUnsigned ? (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-20px" }}
            transition={{ duration: 0.45, delay: 0.1 }}
            role="note"
            aria-label="Unsigned build security warnings"
            className="mt-10 rounded-[1.35rem] border border-amber-200/90 bg-amber-50/90 p-6 sm:p-8"
          >
            <div className="flex items-start gap-3">
              <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-800">
                <AlertTriangle className="h-4 w-4" aria-hidden />
              </span>
              <div>
                <p className="text-base font-semibold text-amber-950">
                  These are early, unsigned builds
                </p>
                <p className="mt-2 max-w-3xl text-sm leading-relaxed text-amber-950/85">
                  We have not yet provisioned Apple or Windows code-signing certificates. On first
                  launch, Windows and macOS will show a real security warning. That is expected for
                  this release — not malware, and not something we are hiding. Signed installers are
                  a separate follow-up once credentials are in place.
                </p>
              </div>
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-2">
              <div className="rounded-2xl border border-amber-100 bg-card p-5 shadow-sm shadow-amber-900/5">
                <p className="text-sm font-semibold text-foreground">
                  Windows — “Windows protected your PC”
                </p>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  SmartScreen may block the installer. Click{" "}
                  <strong className="text-foreground">More info</strong>, then{" "}
                  <strong className="text-foreground">Run anyway</strong>. Only continue if you
                  downloaded from this page or the official GitHub release.
                </p>
              </div>
              <div className="rounded-2xl border border-amber-100 bg-card p-5 shadow-sm shadow-amber-900/5">
                <p className="text-sm font-semibold text-foreground">
                  macOS — “Apple could not verify…” / cannot be opened
                </p>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  In Finder, <strong className="text-foreground">right-click</strong> (or Control-click)
                  the app → <strong className="text-foreground">Open</strong> → confirm{" "}
                  <strong className="text-foreground">Open</strong> again. Or: System Settings → Privacy
                  &amp; Security → <strong className="text-foreground">Open Anyway</strong>.
                </p>
              </div>
            </div>

            <p className="mt-5 text-xs text-amber-900/75">
              Release assets:{" "}
              <a
                href={releaseUrl}
                className="font-semibold underline underline-offset-2 hover:text-amber-950"
                target="_blank"
                rel="noopener noreferrer"
              >
                desktop-v0.1.0 on GitHub
              </a>
              .
            </p>
          </motion.div>
        ) : null}

        <p className="mx-auto mt-10 max-w-2xl text-center text-xs leading-relaxed text-muted-foreground">
          Browser enrichment stays in the Chrome extension — not in Desktop. Full Settings, Meson,
          Agents, and Billing open in the browser from the companion.
        </p>
      </div>
    </section>
  )
}
