"use client"

/**
 * Slice 0 foundation preview — production components (tokens, PageIntro, WM shell).
 * Internal only. Does not mount Intelligence Core / useChat.
 */

import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageIntro } from "@/components/gravitre/page-intro"
import { GravitreWindowManagerShell } from "@/components/gravitre/window-manager"
import { TYPE, PAGE_FAMILY, SEMANTIC } from "@/lib/design-system"
import { cn } from "@/lib/utils"

export function Slice0FoundationPreview() {
  const [dark, setDark] = useState(false)
  const [viewport, setViewport] = useState(1280)
  const [viewportReady, setViewportReady] = useState(false)

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark)
    return () => {
      document.documentElement.classList.remove("dark")
    }
  }, [dark])

  useEffect(() => {
    const onResize = () => setViewport(window.innerWidth)
    onResize()
    setViewportReady(true)
    window.addEventListener("resize", onResize)
    return () => window.removeEventListener("resize", onResize)
  }, [])

  return (
    <div className="min-h-screen bg-[color:var(--g-canvas)] text-[color:var(--g-text-primary)]">
      <div className="mx-auto max-w-6xl space-y-10 px-4 py-8 sm:px-6">
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-[color:var(--g-border-subtle)] pb-4">
          <div>
            <p className={TYPE.eyebrow}>Phase 8 · Slice 0 · production foundation</p>
            <h1 className={cn(TYPE.pageTitle, "mt-1")}>Tokens · primitives · Window Manager</h1>
            <p className={cn(TYPE.pageLead, "mt-2")}>
              G-STRUCT selected. Presentation-only WM. Core runtime untouched. Show-the-work placement-only.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant={dark ? "secondary" : "outline"}
              aria-pressed={dark}
              onClick={() => setDark((v) => !v)}
            >
              {dark ? "Dark" : "Light"}
            </Button>
          </div>
        </header>

        <section data-slice0="tokens" className="space-y-3">
          <h2 className={TYPE.sectionTitle}>0.1 Design tokens</h2>
          <div className="grid gap-3 sm:grid-cols-4">
            {[
              ["Brand", "var(--g-brand)"],
              ["Canvas", "var(--g-canvas)"],
              ["Intelligence", SEMANTIC.intelligence],
              ["WM surface", "var(--g-wm-surface)"],
            ].map(([label, token]) => (
              <div
                key={label}
                className="rounded-[var(--g-radius-card)] border border-[color:var(--g-border-default)] p-3"
              >
                <div
                  className="mb-2 h-10 rounded-[var(--g-radius-tile)] border border-[color:var(--g-border-subtle)]"
                  style={{ background: token }}
                />
                <p className={TYPE.meta}>{label}</p>
                <p className="font-mono text-[10px] text-[color:var(--g-text-muted)]">{token}</p>
              </div>
            ))}
          </div>
          <div className="space-y-1">
            <p className={TYPE.pageTitle}>Page title</p>
            <p className={TYPE.pageLead}>Page lead uses Inter Display via --font-primary.</p>
            <p className={TYPE.eyebrow}>Eyebrow · tracking locked</p>
          </div>
        </section>

        <section data-slice0="primitives" className="space-y-3">
          <h2 className={TYPE.sectionTitle}>0.2 Shared interaction primitives</h2>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button">Primary</Button>
            <Button type="button" variant="secondary">
              Secondary
            </Button>
            <Button type="button" variant="outline">
              Outline
            </Button>
            <Button type="button" variant="ghost">
              Ghost
            </Button>
            <Input className="max-w-xs" placeholder="Field radius (not pill)" aria-label="Sample field" />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {(Object.keys(PAGE_FAMILY) as Array<keyof typeof PAGE_FAMILY>).map((family) => (
              <div
                key={family}
                className="rounded-[var(--g-radius-card)] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] p-4"
              >
                <PageIntro
                  family={family}
                  eyebrow={`Family · ${family}`}
                  title={`${family[0]!.toUpperCase()}${family.slice(1)} intro`}
                  lead="SaaSFrame-informed hierarchy · Nodus/Gravitre tokens."
                  actions={
                    <Button type="button" size="sm">
                      Action
                    </Button>
                  }
                />
              </div>
            ))}
          </div>
        </section>

        <section data-slice0="window-manager" className="space-y-3">
          <h2 className={TYPE.sectionTitle}>0.3 Window Manager presentation shell</h2>
          <p className={TYPE.pageLead}>
            Option A: contextual default + remembered preference. Identity ids stay stable across
            transitions. Viewport hint: {viewportReady ? `${viewport}px` : "…"}
          </p>
          <GravitreWindowManagerShell
            pathname="/dashboard"
            viewportWidth={1280}
            pageContextSlot={
              <div className="p-6">
                <PageIntro
                  family="operating"
                  title="Dashboard (page context)"
                  lead="Visible beside docked AI — not covered by the dock."
                />
              </div>
            }
          />
        </section>
      </div>
    </div>
  )
}
